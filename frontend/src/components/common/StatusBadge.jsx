import { statuses } from '../../utils/formatters.js';
export default function StatusBadge({ status }) {
  const [label, color] = statuses[status] || [status, 'gray'];
  return <span className={`status-badge ${color}`}><span className="status-dot" />{label}</span>;
}

