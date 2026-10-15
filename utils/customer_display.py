"""Presentation-only customer labels; never change stored keys or print payloads."""

import re

import pandas as pd
from pandas.io.formats.style import Styler

from .customer_repository import _mappings, customer_display_name
from .database import connect_from_config


class CustomerDisplay:
    def __init__(self, config):
        self.config = config
        self._names = None

    def _load(self):
        if self._names is None:
            with connect_from_config(self.config) as conn:
                customers = _mappings(conn.execute("SELECT customer_id,name,short_name FROM customers"))
                aliases = _mappings(conn.execute("SELECT alias,customer_id FROM customer_aliases"))
            self._codes = {c['customer_id']: customer_display_name(c) for c in customers}
            self._names = {c['name']: self._codes[c['customer_id']] for c in customers}
            self._names.update({a['alias']: self._codes[a['customer_id']] for a in aliases
                                if a['customer_id'] in self._codes})

    def name(self, value, customer_id=None):
        self._load()
        return self._codes.get(str(customer_id), self._names.get(str(value).strip(), value))

    def label(self, value):
        """Format delimited picker labels without changing the selected value."""
        parts = re.split(r'(\s*[|｜·]\s*|\s+-\s+)', str(value))
        return ''.join(str(self.name(part)) if i % 2 == 0 else part for i, part in enumerate(parts))

    def frame(self, data):
        """Copy only customer columns, preserving row order and editor identities."""
        styled = isinstance(data, Styler)
        frame = data.data if styled else data
        if isinstance(frame, (list, tuple, dict)):
            frame = pd.DataFrame(frame)
        if not isinstance(frame, pd.DataFrame):
            return data
        fields = [c for c in ('客戶名稱', 'customer_name', '客戶顯示') if c in frame.columns]
        if not fields:
            return data
        result = frame.copy()
        code_field = next((c for c in ('客戶編號', 'customer_id') if c in result), None)
        for field in fields:
            result[field] = [self.name(value, result.iloc[i][code_field] if code_field else None)
                             for i, value in enumerate(result[field])]
        # Styler formatters keep all existing colors, number formats and alignment.
        if styled:
            return data.format({field: lambda value: self.name(value) for field in fields})
        return result

    def selectbox(self, target, label, options, *args, **kwargs):
        formatter = kwargs.pop('format_func', str)
        return target.selectbox(label, options, *args,
                                format_func=lambda value: self.label(formatter(value)), **kwargs)
