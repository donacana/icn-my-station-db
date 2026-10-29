import { useState } from 'react';
import { Bell, Clock3, ArrowRightLeft, Users, CloudSun } from 'lucide-react';
import Panel from '../common/Panel.jsx';
import { time } from '../../utils/formatters.js';
const icons = { DELAY: Clock3, GATE_CHANGE: ArrowRightLeft, CONGESTION: Users, WEATHER: CloudSun };
export default function AlertList({ alerts, selectedFlight }) {
  const [filter, setFilter] = useState('all');
  const rows = alerts.filter(alert => filter === 'all' || (filter === 'mine' ? selectedFlight && alert.flightNo === selectedFlight.flightNo : alert.isImportant));
  return <Panel title="스마트 알림" icon={Bell} action={<span className="count-pill">{rows.length}</span>}>
    <div className="text-tabs">{[['all', '전체'], ['mine', '내 항공편'], ['important', '중요 알림']].map(([id, label]) => <button key={id} aria-pressed={filter === id} onClick={() => setFilter(id)}>{label}</button>)}</div>
    <div className="alert-list">{rows.map(alert => {
      const Icon = icons[alert.type] || Bell;
      return <article className={`alert-item ${alert.severity.toLowerCase()}`} key={alert.alertId}><span className="alert-icon"><Icon size={16} /></span><div><div className="alert-title"><h3>{alert.title}</h3><time>{time(alert.createdAt)}</time></div><p>{alert.message}</p></div></article>;
    })}{!rows.length && <p className="empty-state">{selectedFlight ? '선택한 항공편에 대한 알림이 없습니다.' : '항공편을 검색하거나 운항 목록에서 선택해 주세요.'}</p>}</div>
  </Panel>;
}

