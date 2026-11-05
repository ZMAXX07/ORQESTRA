import React from 'react';
import { Button } from './Button';
import './Pagination.css';

export interface PaginationProps {
  currentPage: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (newPage: number) => void;
  disabled?: boolean;
}

export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  pageSize,
  totalItems,
  onPageChange,
  disabled = false,
}) => {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));

  if (totalItems <= pageSize && currentPage === 1) {
    return null;
  }

  const startItem = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  return (
    <nav className="orq-pagination" aria-label="Pagination Navigation">
      <div className="orq-pagination-info">
        Showing <span className="orq-pagination-number">{startItem}</span> to{' '}
        <span className="orq-pagination-number">{endItem}</span> of{' '}
        <span className="orq-pagination-number">{totalItems}</span> items
      </div>

      <div className="orq-pagination-controls">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={disabled || currentPage <= 1}
          aria-label="Go to previous page"
        >
          Previous
        </Button>

        <span className="orq-pagination-current" aria-current="page">
          Page {currentPage} of {totalPages}
        </span>

        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={disabled || currentPage >= totalPages}
          aria-label="Go to next page"
        >
          Next
        </Button>
      </div>
    </nav>
  );
};
