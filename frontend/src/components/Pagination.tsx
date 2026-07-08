import { useEffect, useState } from "react";

interface PaginationProps {
  page: number; // 1-based
  pageSize: number;
  total: number;
  onPage: (p: number) => void;
  label?: string;
}

/** Compact pager shown under a table; renders nothing when it all fits on one page. */
export function Pagination({ page, pageSize, total, onPage, label = "rows" }: PaginationProps) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(total, page * pageSize);
  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-border text-xs text-muted">
      <span>
        {start}–{end} of {total} {label}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          className="px-2.5 py-1 rounded border border-border disabled:opacity-40 hover:border-cyan hover:text-ink"
        >
          Prev
        </button>
        <span className="px-2 tabular-nums">
          {page} / {pages}
        </span>
        <button
          type="button"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
          className="px-2.5 py-1 rounded border border-border disabled:opacity-40 hover:border-cyan hover:text-ink"
        >
          Next
        </button>
      </div>
    </div>
  );
}

/** Slice a list into the current page; auto-snaps back when the list shrinks. */
export function usePaged<T>(items: T[], pageSize: number) {
  const [page, setPage] = useState(1);
  const pages = Math.max(1, Math.ceil(items.length / pageSize));
  const safePage = Math.min(page, pages);

  useEffect(() => {
    if (page > pages) setPage(pages);
  }, [page, pages]);

  return {
    page: safePage,
    setPage,
    pageSize,
    total: items.length,
    slice: items.slice((safePage - 1) * pageSize, safePage * pageSize),
  };
}
