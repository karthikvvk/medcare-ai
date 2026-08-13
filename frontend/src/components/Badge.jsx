import React from 'react';

const priorityClass = {
  CRITICAL: 'badge-critical',
  HIGH: 'badge-high',
  MEDIUM: 'badge-medium',
  LOW: 'badge-low',
  SAFE: 'badge-safe',
  WATCH: 'badge-medium',
  PENDING: 'badge-low',
  APPROVED: 'badge-safe',
  REJECTED: 'badge-critical',
};

export default function Badge({ label }) {
  const cls = priorityClass[label] || 'badge-low';
  return <span className={`badge ${cls}`}>{label}</span>;
}
