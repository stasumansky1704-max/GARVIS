// =============================================================================
// DataTable — Sortable data table component
// =============================================================================

import React, { useState, useMemo } from "react";

interface Column<T> {
  key: string;
  header: string;
  width?: string;
  render?: (row: T) => React.ReactNode;
  sortable?: boolean;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (row: T) => string;
  onRowClick?: (row: T) => void;
  selectedRow?: string | null;
  maxHeight?: number;
}

function DataTable<T>({ columns, data, keyExtractor, onRowClick, selectedRow, maxHeight }: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const sorted = useMemo(() => {
    if (!sortKey) return data;
    return [...data].sort((a, b) => {
      const av = (a as Record<string, unknown>)[sortKey];
      const bv = (b as Record<string, unknown>)[sortKey];
      if (av === bv) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = av < bv ? -1 : 1;
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [data, sortKey, sortDir]);

  return (
    <div style={maxHeight ? { maxHeight, overflow: "auto" } : undefined}>
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                style={{ width: col.width, cursor: col.sortable !== false ? "pointer" : "default" }}
                onClick={() => col.sortable !== false && handleSort(col.key)}
              >
                {col.header}
                {sortKey === col.key && (
                  <span style={{ marginLeft: 4, fontSize: 9 }}>{sortDir === "asc" ? "▲" : "▼"}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const key = keyExtractor(row);
            return (
              <tr
                key={key}
                className={selectedRow === key ? "selected" : ""}
                onClick={() => onRowClick?.(row)}
                style={{ cursor: onRowClick ? "pointer" : "default" }}
              >
                {columns.map((col) => (
                  <td key={col.key}>
                    {col.render
                      ? col.render(row)
                      : String((row as Record<string, unknown>)[col.key] ?? "—")
                    }
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default React.memo(DataTable) as typeof DataTable;
