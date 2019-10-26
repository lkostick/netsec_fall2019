from collections.abc import MutableMapping

class SizedDict(MutableMapping):
    def __init__(self, size=15, data={}, **kw):
        self.maxsize = size
        self._dict = {}
        self._dict.update(data)
        self._dict.update(kw)
    def __getitem__(self, key):
        return self._dict[key]
    def __delitem__(self, key):
        del self._dict[key]
    def __setitem__(self, key, value):
        if key in self._dict:
            self._dict[key] = value
        else:
            if len(self._dict) < self.maxsize:
                self._dict[key] = value
            else:
                raise IndexError(f'{self.__class__.__name__} dict full. Maxsize={self.maxsize}.')
    def __iter__(self):
        return iter(self._dict)
    def __len__(self):
        return len(self._dict)
    def __repr__(self):
        return f"{self._dict}"

