"""
Audit Logger for AI Orchestrator

Provides tamper-evident logging of all AI actions for compliance and debugging.

How the tamper evidence works, and what it can and cannot prove
---------------------------------------------------------------
Every entry stores a SHA256 of its own content (``hash``) and the ``hash`` of the
entry before it (``previous_hash``). Changing, reordering or deleting an entry
therefore breaks the chain at that point, and verification walks the chain from
the start to the end to find the first break.

Two things follow from the log being *rotated*, and both used to be reported
wrongly:

* Entries live in several files once the log rotates. The current file is
  unnumbered (``audit.log``); the most recent backup is ``audit.log.1`` and
  older backups have HIGHER numbers (``audit.log.2``, ``audit.log.3`` ...),
  because the standard logging rotation shifts ``.n`` to ``.n+1`` on each
  rollover. The chain therefore runs from the highest existing number down to
  the unnumbered current file.
* Rotating away the oldest segment removes the entry that the next oldest
  entry's ``previous_hash`` points at. That is normal housekeeping, NOT
  tampering, and must not be reported as a broken chain. Verification uses a
  small sidecar state file (``audit.chain.json``) to remember which
  ``previous_hash`` the oldest retained entry is expected to carry, so the check
  can still start from a known root instead of crying wolf after every rotation.

What this cannot prove: entries are not signed and there is no secret involved,
so anyone who can write to the log directory (or who holds the API token and
can make the orchestrator write an entry) can add entries that verify as
genuine. The chain proves *nobody changed history unnoticed*; it does not prove
who wrote it. Treat a valid chain as "not edited", not as "authentic".

Failure policy: verification failures are reported loudly (ERROR level and the
``/api/v1/audit/verify`` payload) but never block startup - the orchestrator
must still be able to explain the bot's behaviour, which is exactly when the
operator needs it most.
"""

import json
import logging
import hashlib
import os
import re
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import aiofiles
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)

# The value the very first entry of the whole log carries as ``previous_hash``:
# JSON ``null``. Nothing precedes it, so there is nothing to point at. This is
# the sentinel the original chain verification already used (it started walking
# with ``previous_hash = None``); it is named here so the sidecar state file and
# the verifier cannot drift apart.
GENESIS_PREVIOUS_HASH: Optional[str] = None

# Sidecar recording the chain root. Kept separate from the log itself because the
# log's first line is exactly the thing rotation deletes.
CHAIN_STATE_FILENAME = "audit.chain.json"

# ``<log name>.<number>`` is the standard logging rotation naming.
_SEGMENT_SUFFIX_TEMPLATE = r"^{}\.(\d+)$"


@dataclass
class AuditEntry:
    """Single audit log entry."""
    timestamp: str
    action_id: str
    plugin: str
    action: str
    user_initiated: bool
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    decision_reasoning: str
    risk_level: str  # low, medium, high, critical
    approved_by: Optional[str] = None
    approval_timestamp: Optional[str] = None
    hash: Optional[str] = None
    previous_hash: Optional[str] = None

    def compute_hash(self) -> str:
        """Compute SHA256 hash of this entry (excluding hash field)."""
        data = asdict(self)
        data.pop("hash", None)
        data.pop("previous_hash", None)
        content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _entry_hash_from_dict(entry: Dict[str, Any]) -> str:
    """Recompute an entry's hash from the raw dict read off disk.

    Kept as a free function (rather than only ``AuditEntry.compute_hash``) so
    verification hashes exactly what was written, even if a line contains fields
    this version of ``AuditEntry`` does not know about. Hashing a re-serialised
    dataclass could silently drop an unknown field and mask an edit.
    """
    return hashlib.sha256(
        json.dumps(
            {k: v for k, v in entry.items() if k not in ["hash", "previous_hash"]},
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()


class _ChainRootRotatingFileHandler(RotatingFileHandler):
    """Rotating handler that keeps the chain-root sidecar in step with rotation.

    Why a subclass rather than a scheduled task: the moment entries are shifted
    from one segment to another is precisely the moment the retained history
    changes shape, and the only reliable place to notice it is inside the
    rollover itself. Subclassing the standard handler keeps all of its file
    handling (including cloud/rename hooks) intact - we only observe.

    Both callbacks fail soft: a problem updating the sidecar must never cost us
    an audit entry.
    """

    def __init__(self, *args, on_rollover=None, **kwargs):
        self._on_rollover = on_rollover
        super().__init__(*args, **kwargs)

    def doRollover(self):  # noqa: N802 - name fixed by the stdlib base class
        super().doRollover()
        callback = self._on_rollover
        if callback is None:
            return
        try:
            callback()
        except Exception:  # noqa: BLE001 - logging must not die on bookkeeping
            logger.exception("Could not update the audit chain-root state file after rotation")


class AuditLogger:
    """
    Tamper-evident audit logger with hash chaining.
    Each entry includes hash of previous entry for integrity verification.
    """

    def __init__(
        self,
        log_dir: str = "/app/logs/audit",
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 10,
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "audit.log"
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._last_hash: Optional[str] = None

        # Which ``previous_hash`` the OLDEST retained entry is expected to carry,
        # and whether we actually know it. ``_chain_root_known`` is False when the
        # sidecar is missing or unreadable and the retained history does not begin
        # at the genesis entry, i.e. when we cannot prove where the retained
        # history starts.
        self.chain_state_file = self.log_dir / CHAIN_STATE_FILENAME
        self._expected_root_previous_hash: Optional[str] = GENESIS_PREVIOUS_HASH
        self._chain_root_known: bool = True
        self._chain_root_adopted: bool = False

        # Load (or establish) the chain root BEFORE the handler exists, so a
        # rollover can never fire against a blank state.
        self._load_chain_state()

        self._setup_logger()
        self._load_last_hash()

    def _setup_logger(self):
        """Setup rotating file handler for audit logs.

        The handler is a small subclass that refreshes the chain-root sidecar at
        each rollover; see ``_ChainRootRotatingFileHandler``.
        """
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        # Clear existing handlers
        self.logger.handlers.clear()

        handler = _ChainRootRotatingFileHandler(
            self.log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            on_rollover=self._sync_chain_root_after_rollover,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(handler)

    # ------------------------------------------------------------------
    # Chain state (the recorded start of the retained chain)
    # ------------------------------------------------------------------

    def _chain_segments(self) -> List[Path]:
        """Return every on-disk log segment, oldest first, current file last.

        Rotated backups are named ``audit.log.1`` (most recent) through
        ``audit.log.N`` (oldest) by the standard logging rotation, so sorting the
        numeric suffix in DESCENDING order and appending the unnumbered current
        file yields true chronological order. Sorting by file mtime would be
        wrong: a copy, restore or rsync can hand the files any timestamps at all.
        Gaps in the numbering are fine - the remaining files are still ordered.
        """
        segments: List[Path] = []
        pattern = _SEGMENT_SUFFIX_TEMPLATE.format(re.escape(self.log_file.name))
        try:
            numbered: List[Tuple[int, Path]] = []
            for path in self.log_dir.iterdir():
                match = re.match(pattern, path.name)
                if not match:
                    continue
                try:
                    if not path.is_file():
                        continue
                except OSError:
                    continue
                numbered.append((int(match.group(1)), path))
            numbered.sort(key=lambda item: item[0], reverse=True)
            segments = [path for _, path in numbered]
        except OSError:
            logger.exception("Could not list audit log segments in %s", self.log_dir)

        try:
            if self.log_file.is_file():
                segments.append(self.log_file)
        except OSError:
            pass
        return segments

    def _read_segment_lines(self, path: Path) -> List[str]:
        """Read a segment as text lines, tolerating an unreadable file.

        Used by the query helpers, where losing one unreadable file should still
        return the entries that CAN be read. Verification uses
        ``_read_segment_lines_strict`` instead: there, an unreadable segment must
        be a reported failure, not a silent gap in the history.
        """
        lines = self._read_segment_lines_strict(path)
        if lines is None:
            logger.error("Could not read audit log segment %s", path)
            return []
        return lines

    @staticmethod
    def _read_segment_lines_strict(path: Path) -> Optional[List[str]]:
        """Read a segment, or return None when it cannot be read at all."""
        try:
            with open(path, "r") as f:
                return f.readlines()
        except OSError:
            return None

    @staticmethod
    def _parse_line(line: str) -> Optional[Dict[str, Any]]:
        """Parse one JSONL line into a dict, or None when it is not one."""
        stripped = line.strip()
        if not stripped:
            return None
        try:
            data = json.loads(stripped)
        except (ValueError, TypeError):
            return None
        return data if isinstance(data, dict) else None

    def _first_entry_previous_hash(self, path: Path) -> Tuple[str, Optional[str]]:
        """Return ``(state, previous_hash)`` for the first entry of a segment.

        ``state`` is ``"found"`` (a parseable entry was read), ``"empty"`` (the
        segment has no entries yet - normal for a freshly rolled current file) or
        ``"unreadable"`` (missing, unreadable or first line corrupt). Callers
        must not treat ``"unreadable"`` as a hash value: adopting a corrupt line
        as the chain root would launder exactly the tampering this protects
        against.
        """
        try:
            if not path.is_file():
                return ("empty", None)
            with open(path, "r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    entry = self._parse_line(line)
                    if entry is None:
                        # The FIRST real line is unreadable. Do not skip past it
                        # to the next entry: the next entry's previous_hash would
                        # then be adopted as the chain root, hiding the damage.
                        return ("unreadable", None)
                    return ("found", entry.get("previous_hash"))
                return ("empty", None)
        except OSError:
            logger.error("Could not read the first entry of audit log segment %s", path)
            return ("unreadable", None)

    def _load_chain_state(self) -> None:
        """Load, or establish, the recorded chain root.

        Cases, and why each is handled the way it is:

        * A state file exists - use it. This is the normal path and it is what
          makes "the chain is intact" a provable statement rather than a guess.
        * No state file but the oldest retained entry is the genesis entry
          (``previous_hash`` null) - we are at the true start of the log, so
          record that.
        * No state file and the oldest retained entry points somewhere already
          rotated away - the history was already truncated before this state file
          existed. We ADOPT the observed value so verification works, but flag it
          (``_chain_root_adopted``) so reports say out loud that front-truncation
          before this point cannot be ruled out. We never invent a hash.
        * No state file and the oldest first line is unreadable - root unknown.

        None of this raises: an audit logger that cannot prove its own root is
        still far more useful than an orchestrator that refuses to start.
        """
        try:
            if self.chain_state_file.is_file():
                with open(self.chain_state_file, "r") as f:
                    state = json.load(f)
                if isinstance(state, dict) and "expected_root_previous_hash" in state:
                    root = state.get("expected_root_previous_hash")
                    self._expected_root_previous_hash = root
                    self._chain_root_known = True
                    self._chain_root_adopted = bool(state.get("adopted", False))
                    return
                logger.error(
                    "Audit chain state file %s is not readable as the expected "
                    "object; the start of the audit chain cannot be confirmed.",
                    self.chain_state_file,
                )
                self._chain_root_known = False
                return
        except (OSError, ValueError, TypeError):
            logger.exception(
                "Could not read the audit chain state file %s; the start of the "
                "audit chain cannot be confirmed.",
                self.chain_state_file,
            )
            self._chain_root_known = False
            return

        # No state file yet.
        segments = self._chain_segments()
        if not segments:
            # Brand new installation.
            self._expected_root_previous_hash = GENESIS_PREVIOUS_HASH
            self._chain_root_known = True
            self._write_chain_state(reason="initial")
            return

        state, observed = self._first_entry_previous_hash(segments[0])
        if state == "found" and observed == GENESIS_PREVIOUS_HASH:
            # Retained history starts at the very first entry ever written.
            self._expected_root_previous_hash = GENESIS_PREVIOUS_HASH
            self._chain_root_known = True
            self._write_chain_state(reason="initial")
            return
        if state == "found":
            self._expected_root_previous_hash = observed
            self._chain_root_known = True
            self._chain_root_adopted = True
            logger.warning(
                "No audit chain state file was present; adopting the "
                "previous_hash of the oldest retained audit entry as the chain "
                "root. Entries removed from the FRONT of the log before this "
                "point cannot be detected.",
            )
            self._write_chain_state(reason="adopted_from_oldest_segment")
            return

        # "empty" or "unreadable": nothing to pin the chain to.
        self._chain_root_known = False
        logger.warning(
            "Could not determine the start of the audit chain (%s); chain "
            "verification will report the root as unverified.",
            state,
        )

    def _write_chain_state(self, reason: str = "update") -> None:
        """Persist the chain-root sidecar atomically. Never raises.

        Written to a temporary file in the same directory and moved into place
        with ``os.replace`` so a crash mid-write cannot leave a half-written
        state file that would later be read as "the root is garbage".
        """
        payload = {
            "version": 1,
            "description": (
                "Expected previous_hash of the OLDEST retained audit log entry. "
                "Used to verify the hash chain across rotated segments without "
                "mistaking normal rotation for tampering."
            ),
            "genesis_previous_hash": GENESIS_PREVIOUS_HASH,
            "expected_root_previous_hash": self._expected_root_previous_hash,
            "adopted": self._chain_root_adopted,
            "reason": reason,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        tmp_path = self.chain_state_file.with_name(self.chain_state_file.name + ".tmp")
        try:
            with open(tmp_path, "w") as f:
                json.dump(payload, f, indent=2, sort_keys=True)
                f.write("\n")
            os.replace(tmp_path, self.chain_state_file)
        except OSError:
            logger.exception(
                "Could not write the audit chain state file %s; future "
                "verification may be unable to confirm the chain root.",
                self.chain_state_file,
            )
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass

    def _sync_chain_root_after_rollover(self) -> None:
        """Advance the recorded chain root after a rotation. Never raises.

        Rotation is the only thing that legitimately changes which entry is
        oldest. When the oldest segment is dropped (the log has reached
        ``backup_count`` segments and the numbers shift up), the new oldest
        entry's ``previous_hash`` points at an entry that no longer exists on
        disk: that value becomes the new root. When nothing was dropped the
        observed value is unchanged and this is a no-op.

        Note this deliberately writes only to the sidecar and to the module
        logger. Writing through ``self.logger`` would inject a plain-text line
        into the JSONL audit log and corrupt the very chain being protected.
        """
        segments = self._chain_segments()
        if not segments:
            return
        state, observed = self._first_entry_previous_hash(segments[0])
        if state != "found":
            logger.warning(
                "Audit log rotated but the oldest segment (%s) could not be read "
                "(%s); the recorded chain root was left unchanged.",
                segments[0].name,
                state,
            )
            return
        if observed == self._expected_root_previous_hash:
            return
        self._expected_root_previous_hash = observed
        self._chain_root_known = True
        self._write_chain_state(reason="rotation")
        logger.info(
            "Audit log rotated: the oldest retained segment is now %s, so the "
            "expected chain root advanced.",
            segments[0].name,
        )

    def _load_last_hash(self):
        """Load the hash of the last entry for chaining, across all segments.

        Why not just the current file: a rollover happens *while* writing, so the
        current file normally has content. But if the process restarts between a
        rollover and the next entry, the current file is empty, and taking the
        last hash from it would start the new entry's chain at ``null`` - a real
        break in a chain that was never touched. Walking back through the
        segments to the newest entry that actually exists keeps the chain
        continuous.
        """
        for path in reversed(self._chain_segments()):
            lines = self._read_segment_lines(path)
            for line in reversed(lines):
                data = self._parse_line(line)
                if data is None:
                    continue
                self._last_hash = data.get("hash")
                return
        self._last_hash = None

    def _verify_chain_detailed(self) -> Dict[str, Any]:
        """Walk the whole chain, oldest segment to current file, and report.

        Returns a dict with:

        * ``valid`` - True unless a break was actually found. Rotation alone is
          never a break.
        * ``status`` - ``"no_log"``, ``"intact"``, ``"intact_rotated"`` or
          ``"broken"``. ``"intact_rotated"`` exists so a shifted/rotated log is
          not misreported as a failure: the old verifier only read the current
          file, so after the first rotation the first line's ``previous_hash``
          matched nothing and every check reported ``valid: false``. A safety
          report that alarms on normal housekeeping teaches the operator to
          ignore it, which is worse than saying nothing.
        * ``root_verified`` / ``history_truncated`` - whether the start of the
          retained history is a known root (see ``_load_chain_state``), and
          whether entries are known to have been rotated or removed from the
          front. These are what let a reader tell "nothing was edited" apart from
          "the earliest part of the history is gone".
        * ``break_location`` / ``message`` - where it broke and what that means
          in plain language.

        A corrupt line counts as a break: silently skipping unparseable lines
        would hide tampering. Blank lines are ignored as whitespace.
        """
        segments = self._chain_segments()
        result: Dict[str, Any] = {
            "valid": True,
            "status": "no_log",
            "message": "No audit entries have been written yet.",
            "entry_count": 0,
            "segments": [path.name for path in segments],
            "rotated": len(segments) > 1,
            "root_verified": self._chain_root_known,
            "history_truncated": False,
            "break_location": None,
            "oldest_entry_timestamp": None,
            "notes": [],
            "last_hash": None,
        }

        if not segments:
            return result

        if self._chain_root_adopted:
            result["notes"].append(
                "The chain root was adopted from the oldest retained entry "
                "(no chain state file existed at the time), so entries removed "
                "from the front of the log before that point cannot be detected."
            )

        expected_previous = (
            self._expected_root_previous_hash
            if self._chain_root_known
            else GENESIS_PREVIOUS_HASH
        )
        root_verified = self._chain_root_known
        first_previous_hash: Optional[str] = None
        previous_hash: Optional[str] = expected_previous
        entry_count = 0
        last_hash: Optional[str] = None
        oldest_timestamp: Optional[str] = None

        for path in segments:
            lines = self._read_segment_lines_strict(path)
            if lines is None:
                return self._broken_result(
                    result,
                    path,
                    0,
                    "this log segment exists but could not be read, so its "
                    "entries cannot be verified (permissions, I/O error or a "
                    "file that is not a regular file)",
                    entry_count,
                    last_hash,
                )
            for line_num, line in enumerate(lines, 1):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except (ValueError, TypeError):
                    return self._broken_result(
                        result,
                        path,
                        line_num,
                        "the line is not valid JSON (the entry was truncated, "
                        "garbled or rewritten)",
                        entry_count,
                        last_hash,
                    )
                if not isinstance(entry, dict):
                    return self._broken_result(
                        result,
                        path,
                        line_num,
                        "the line is JSON but not an audit entry object",
                        entry_count,
                        last_hash,
                    )

                stored_hash = entry.get("hash")
                stored_previous_hash = entry.get("previous_hash")

                if entry_count == 0:
                    # First retained entry: this is the chain root.
                    first_previous_hash = stored_previous_hash
                    if stored_previous_hash != expected_previous:
                        # The only link that can legitimately be missing: history
                        # in front of it was rotated away (or the state file
                        # missed a rollover). Everything from here on is still
                        # fully verifiable, so report it rather than alarming.
                        root_verified = False
                        result["notes"].append(
                            "The oldest retained audit entry points at an entry "
                            "that is no longer on disk (chain root "
                            "unverified). Older history was rotated out, or "
                            "removed; entries that remain are verified against "
                            "each other."
                        )
                        logger.warning(
                            "Audit chain root unverified: oldest retained entry "
                            "in %s expects previous_hash=%r but the recorded "
                            "root is %r. Treating the front of the log as "
                            "rotated away; verifying the retained chain.",
                            path.name,
                            stored_previous_hash,
                            expected_previous,
                        )
                        previous_hash = stored_previous_hash
                    else:
                        # The retained history starts exactly where we expected,
                        # so the root IS confirmed - whether that came from the
                        # state file or from recognising the genesis sentinel.
                        root_verified = True
                        previous_hash = expected_previous
                        if not self._chain_root_known:
                            # The state file was missing/corrupt but the retained
                            # history demonstrably starts at the genesis entry,
                            # so the root really is known. Record it so the
                            # complaint does not repeat forever.
                            self._expected_root_previous_hash = stored_previous_hash
                            self._chain_root_known = True
                            self._write_chain_state(reason="reconciled_on_verify")

                if stored_previous_hash != previous_hash:
                    return self._broken_result(
                        result,
                        path,
                        line_num,
                        "this entry's previous_hash does not match the hash of "
                        "the entry before it, so an entry was changed, "
                        "reordered, inserted or deleted here",
                        entry_count,
                        last_hash,
                    )

                computed_hash = _entry_hash_from_dict(entry)
                if computed_hash != stored_hash:
                    return self._broken_result(
                        result,
                        path,
                        line_num,
                        "this entry's content no longer matches its own stored "
                        "hash, so the entry was edited after it was written",
                        entry_count,
                        last_hash,
                    )

                previous_hash = stored_hash
                last_hash = stored_hash
                if entry_count == 0:
                    oldest_timestamp = entry.get("timestamp")
                    # Heal a root that drifted without the state file being
                    # updated (for example a crash between rollover and the
                    # sidecar write). Only ever AFTER the observed value has been
                    # reported and logged as unverified.
                    if not root_verified:
                        self._expected_root_previous_hash = stored_previous_hash
                        self._chain_root_known = True
                        self._write_chain_state(reason="reconciled_on_verify")
                entry_count += 1

        rotated = len(segments) > 1
        history_truncated = (
            not root_verified or first_previous_hash != GENESIS_PREVIOUS_HASH
        )
        result.update(
            {
                "valid": True,
                # An empty log is not "intact": there is nothing to have verified.
                # Saying "intact" over zero entries would let a log that was
                # emptied (or never written) look healthy.
                "status": (
                    "no_log"
                    if entry_count == 0
                    else ("intact_rotated" if rotated else "intact")
                ),
                "entry_count": entry_count,
                "root_verified": root_verified,
                "history_truncated": history_truncated,
                "oldest_entry_timestamp": oldest_timestamp,
                "last_hash": last_hash,
            }
        )
        if entry_count == 0:
            result["message"] = (
                "No audit entries are present at all. Nothing has been verified: "
                "this is not a statement that the trail is intact."
            )
        elif rotated:
            result["message"] = (
                f"Audit log chain is intact across {entry_count} entries in "
                f"{len(segments)} log segments. Older entries were rotated out to "
                "keep the files small - rotation is normal maintenance and is NOT "
                "a sign of tampering."
            )
        else:
            result["message"] = (
                f"Audit log chain is intact: {entry_count} entries verified end "
                "to end."
            )
        return result

    def _broken_result(
        self,
        result: Dict[str, Any],
        path: Path,
        line_num: int,
        reason: str,
        entry_count: int,
        last_hash: Optional[str],
    ) -> Dict[str, Any]:
        """Build the "chain is broken" report and shout about it in the logs.

        Logged through the module logger, never through ``self.logger``: the
        audit logger's own handler writes raw messages into the audit log, so an
        error line there would corrupt the JSONL chain it is complaining about.
        """
        message = (
            f"AUDIT LOG CHAIN BROKEN at {path.name} line {line_num}: {reason}. "
            "Everything after this point is unreliable and the audit trail may "
            "have been altered or damaged. Do not rely on it as a record until "
            "this is explained."
        )
        logger.error("%s (audit log directory: %s)", message, self.log_dir)
        result.update(
            {
                "valid": False,
                "status": "broken",
                "message": message,
                "entry_count": entry_count,
                "break_location": {"segment": path.name, "line": line_num},
                "last_hash": last_hash,
            }
        )
        result["notes"].append(
            "A broken chain means at least one entry was modified, reordered, "
            "inserted or deleted while the log was on disk. Treat the audit "
            "trail as untrustworthy and investigate who can write to "
            f"{self.log_dir}."
        )
        return result

    def _verify_chain(self) -> bool:
        """Verify the integrity of the audit log chain.

        Boolean view kept for existing callers; use ``verify_integrity()`` for
        the full picture (rotation vs. genuine break).
        """
        detailed = self._verify_chain_detailed()
        if not detailed["valid"]:
            # Already logged at ERROR level by _broken_result; repeat the top
            # line here so a caller that only uses this boolean still leaves a
            # trace in the logs.
            logger.error("Audit log integrity check FAILED: %s", detailed["message"])
        return bool(detailed["valid"])

    async def log(
        self,
        plugin: str,
        action: str,
        user_initiated: bool,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        decision_reasoning: str,
        risk_level: str = "low",
        approved_by: Optional[str] = None,
    ) -> AuditEntry:
        """
        Log an AI action with full audit trail.
        """
        entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            action_id=hashlib.sha256(
                f"{plugin}{action}{datetime.utcnow().isoformat()}".encode()
            ).hexdigest()[:16],
            plugin=plugin,
            action=action,
            user_initiated=user_initiated,
            input_data=input_data,
            output_data=output_data,
            decision_reasoning=decision_reasoning,
            risk_level=risk_level,
            approved_by=approved_by,
            approval_timestamp=datetime.utcnow().isoformat() + "Z" if approved_by else None,
            previous_hash=self._last_hash,
        )

        entry.hash = entry.compute_hash()
        self._last_hash = entry.hash

        # Write to log
        self.logger.info(json.dumps(entry.to_dict(), default=str))

        # Also write to daily JSONL file for easy querying
        daily_file = self.log_dir / f"audit_{datetime.utcnow().strftime('%Y%m%d')}.jsonl"
        async with aiofiles.open(daily_file, "a") as f:
            await f.write(json.dumps(entry.to_dict(), default=str) + "\n")

        return entry

    async def log_config_change(
        self,
        plugin: str,
        config_changes: Dict[str, Any],
        reasoning: str,
        user_initiated: bool = True,
        approved_by: Optional[str] = None,
    ) -> AuditEntry:
        """Log a configuration change."""
        return await self.log(
            plugin=plugin,
            action="config_change",
            user_initiated=user_initiated,
            input_data={"changes": config_changes},
            output_data={"status": "pending_approval" if not approved_by else "applied"},
            decision_reasoning=reasoning,
            risk_level="high",
            approved_by=approved_by,
        )

    async def log_trade_decision(
        self,
        plugin: str,
        pair: str,
        decision: str,
        reasoning: str,
        confidence: float,
        market_context: Dict[str, Any],
        approved_by: Optional[str] = None,
    ) -> AuditEntry:
        """Log a trading decision."""
        risk_level = "critical" if decision in ["buy", "sell"] else "medium"
        return await self.log(
            plugin=plugin,
            action="trade_decision",
            user_initiated=False,
            input_data={
                "pair": pair,
                "decision": decision,
                "confidence": confidence,
                "market_context": market_context,
            },
            output_data={"executed": approved_by is not None},
            decision_reasoning=reasoning,
            risk_level=risk_level,
            approved_by=approved_by,
        )

    async def log_strategy_generation(
        self,
        strategy_code: str,
        pair: str,
        reasoning: str,
        backtest_results: Optional[Dict[str, Any]] = None,
        approved_by: Optional[str] = None,
    ) -> AuditEntry:
        """Log strategy generation."""
        return await self.log(
            plugin="strategy_generator",
            action="generate_strategy",
            user_initiated=False,
            input_data={
                "pair": pair,
                "backtest_results": backtest_results or {},
            },
            output_data={
                "strategy_hash": hashlib.sha256(strategy_code.encode()).hexdigest()[:16],
                "code_length": len(strategy_code),
            },
            decision_reasoning=reasoning,
            risk_level="high",
            approved_by=approved_by,
        )

    def _iter_entry_dicts_newest_first(self):
        """Yield parsed entries from newest to oldest, across every segment.

        Why across segments: reading only the current file made recent history
        silently disappear the moment the log rotated, so ``/api/v1/audit/recent``
        could show an empty or near-empty trail right after a rotation even
        though the entries existed. Newest-first also lets callers stop as soon
        as they have enough entries instead of parsing the whole 10 x 10MB.
        """
        for path in reversed(self._chain_segments()):
            for line in reversed(self._read_segment_lines(path)):
                data = self._parse_line(line)
                if data is not None:
                    yield data

    def get_recent_entries(self, limit: int = 100) -> List[AuditEntry]:
        """Get recent audit entries, newest last, spanning rotated segments."""
        collected: List[AuditEntry] = []
        if limit <= 0:
            return collected
        for data in self._iter_entry_dicts_newest_first():
            try:
                collected.append(AuditEntry(**data))
            except TypeError:
                # An entry written by a different version; skip it rather than
                # losing the rest of the history.
                continue
            if len(collected) >= limit:
                break
        collected.reverse()  # callers expect oldest -> newest, as before
        return collected

    def get_entries_by_plugin(self, plugin: str, limit: int = 100) -> List[AuditEntry]:
        """Entries for one plugin, most recent first, across all segments."""
        entries: List[AuditEntry] = []
        if limit <= 0:
            return entries
        for data in self._iter_entry_dicts_newest_first():
            if data.get("plugin") != plugin:
                continue
            try:
                entries.append(AuditEntry(**data))
            except TypeError:
                continue
            if len(entries) >= limit:
                break
        return entries  # already most recent first

    def get_entries_by_risk_level(self, risk_level: str, limit: int = 100) -> List[AuditEntry]:
        """Entries of one risk level, most recent first, across all segments."""
        entries: List[AuditEntry] = []
        if limit <= 0:
            return entries
        for data in self._iter_entry_dicts_newest_first():
            if data.get("risk_level") != risk_level:
                continue
            try:
                entries.append(AuditEntry(**data))
            except TypeError:
                continue
            if len(entries) >= limit:
                break
        return entries

    def verify_integrity(self) -> Dict[str, Any]:
        """Verify audit log integrity and describe the result honestly.

        The payload distinguishes three outcomes that used to be conflated:

        * ``status == "intact"`` - chain verified end to end, ``valid: true``.
        * ``status == "intact_rotated"`` - chain verified end to end ACROSS
          rotated segments, ``valid: true``. Rotation is routine maintenance and
          is explicitly not a failure; reporting it as one (as the previous
          current-file-only check did) produced a permanent false alarm once the
          log had rotated once, which is how operators learn to ignore alarms.
        * ``status == "broken"`` - a genuine break: ``valid: false``, the exact
          segment and line, an ERROR-level log line, and a plain-language
          explanation. Never silently swallowed.

        Read ``root_verified`` / ``history_truncated`` alongside ``valid``: a
        valid chain means nothing in the retained history was edited; it does not
        by itself prove that nothing was ever dropped from the front. When
        ``root_verified`` is false the payload says so and adds a note.
        """
        detailed = self._verify_chain_detailed()
        return {
            "valid": bool(detailed["valid"]),
            "status": detailed["status"],
            "message": detailed["message"],
            "entry_count": detailed["entry_count"],
            "last_hash": self._last_hash or detailed.get("last_hash"),
            "log_file": str(self.log_file),
            "segments": detailed["segments"],
            "rotated": detailed["rotated"],
            "history_truncated": detailed["history_truncated"],
            "root_verified": detailed["root_verified"],
            "oldest_entry_timestamp": detailed["oldest_entry_timestamp"],
            "break_location": detailed["break_location"],
            "notes": detailed["notes"],
        }

    async def export_audit_trail(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Export audit trail for date range, including rotated segments.

        A compliance export that quietly omits everything older than the last
        rotation is worse than no export, because it looks complete.
        """
        entries = []
        for path in self._chain_segments():
            for line in self._read_segment_lines(path):
                data = self._parse_line(line)
                if data is None:
                    continue
                try:
                    entry_time = datetime.fromisoformat(
                        data["timestamp"].replace("Z", "+00:00")
                    )
                except (KeyError, TypeError, ValueError):
                    continue
                if start_date and entry_time < start_date:
                    continue
                if end_date and entry_time > end_date:
                    continue
                entries.append(data)
        return entries