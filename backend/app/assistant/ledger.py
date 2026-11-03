"""
The piece ledger: how the model names a piece without ever seeing a database id (step 3c).

One ledger lives for ONE turn. Every piece a tool shows the model gets a small number (1, 2, 3...), and the model
writes {2} in its answer or passes 2 to a tool. Only this turn's numbers exist, so the model cannot name a piece
it was not shown, and it cannot guess an id: it never sees one.
"""


class PieceLedger:
    def __init__(self):
        self._ids = []                      # position i holds the item id of ref i + 1

    def add(self, item_id):
        """The ref of this item; the same item always keeps the same ref."""
        item_id = str(item_id)
        if item_id not in self._ids:
            self._ids.append(item_id)
        return self._ids.index(item_id) + 1

    def item_id(self, ref):
        """The item id behind a ref, or None when this turn never showed that number."""
        return self._ids[ref - 1] if isinstance(ref, int) and 1 <= ref <= len(self._ids) else None

    def refs(self):
        """{ref: item id} for every piece shown this turn."""
        return {i + 1: item_id for i, item_id in enumerate(self._ids)}
