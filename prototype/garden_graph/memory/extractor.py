"""MessageSignificanceExtractor

Utility to scan the *recent N* messages of a conversation and decide which
ones are significant enough to be persisted as memories.  It delegates the
actual *significance scoring* to ``MemoryManager._analyze_message_llm`` so we
inherit the same logic & personalisation already used elsewhere.

Typical usage::

    mm = MemoryManager()
    extractor = MessageSignificanceExtractor(mm)
    idxs = extractor.extract("eve", recent_msgs, recent_is_user, llm)
    # idxs now contains indices (into recent_msgs) that should be saved.

The extractor **does not** create memories by itself – it only returns the
indices/texts that meet the configured threshold.  Higher-level code can then
call ``MemoryManager.analyze_message`` or ``create`` accordingly.
"""
from __future__ import annotations

from typing import List, Sequence

from .manager import MemoryManager, MEM_SIGNIFICANCE_THRESHOLD  # type: ignore


class MessageSignificanceExtractor:
    """Select significant messages from a recent conversation window."""

    def __init__(
        self,
        memory_manager: MemoryManager,
        *,
        threshold: float | None = None,
        window: int | None = None,
    ) -> None:
        """Args:
        memory_manager: existing ``MemoryManager`` whose analysis logic we want
            to reuse.
        threshold: absolute significance (\|score\|) required – if *None*, the
            global ``MEM_SIGNIFICANCE_THRESHOLD`` from config is used.
        window: if given, only the *last* ``window`` messages of the provided
            history are considered.
        """
        self.mm = memory_manager
        self.threshold = threshold if threshold is not None else MEM_SIGNIFICANCE_THRESHOLD
        self.window = window

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    def extract(
        self,
        character_id: str,
        messages: Sequence[str],
        is_user_message: Sequence[bool] | None = None,
        *,
        llm=None,
    ) -> List[int]:
        """Return indices of *messages* deemed significant.

        ``messages`` – list of conversation texts ordered oldest→newest.
        ``is_user_message`` – optional list (same length) marking which texts
        belong to the *human user*; if omitted, we treat **all** messages as
        user-originated because, for memory purposes, we care about what the
        persona perceives from outside.
        """
        if self.window is not None and self.window > 0:
            # slice only the last N messages but keep original indices
            start_idx = max(0, len(messages) - self.window)
            subset = range(start_idx, len(messages))
        else:
            subset = range(len(messages))

        if is_user_message is None:
            is_user_message = [True] * len(messages)

        significant: List[int] = []
        for idx in subset:
            text = messages[idx]
            try:
                # We only want the *score* – not to create a record yet.
                score, *_ = self.mm._analyze_message_llm(character_id, text, llm=llm)  # pylint: disable=protected-access
            except Exception:
                # On any failure just skip the message.
                continue

            if abs(score) >= self.threshold:
                significant.append(idx)

        return significant

    # Convenience --------------------------------------------------------
    def extract_texts(
        self,
        character_id: str,
        messages: Sequence[str],
        is_user_message: Sequence[bool] | None = None,
        *,
        llm=None,
    ) -> List[str]:
        """Return the *texts* of significant messages (wrapper over ``extract``)."""
        idxs = self.extract(character_id, messages, is_user_message, llm=llm)
        return [messages[i] for i in idxs]
