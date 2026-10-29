import { PieChart as PieIcon } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import Panel from '../common/Panel.jsx';
import { statuses } from '../../utils/formatters.js';
const colors = { NORMAL: '#24a782', DELAYED: '#ef754f', CANCELLED: '#9aa6b7', DIVERTED: '#8772d7' };
export default function FlightStatistics({ stats }) {
  return <Panel title="운항 통계" icon={PieIcon} action={<span className="quiet-label">{stats.direction === 'DEPARTURE' ? '출발' : '도착'} 표본</span>}>
    <div className="donut-wrap" role="img" aria-label={`전체 ${stats.total}편. ${stats.breakdown.map(item => `${statuses[item.category][0]} ${item.count}편`).join(', ')}`}>
      <ResponsiveContainer width="100%" height={190}><PieChart><Pie data={stats.breakdown} dataKey="count" nameKey="category" innerRadius={61} outerRadius={80} paddingAngle={3} stroke="none" isAnimationActive={false}>{stats.breakdown.map(item => <Cell key={item.category} fill={colors[item.category]} />)}</Pie><Tooltip formatter={(value, name) => [`${value}편`, statuses[name]?.[0] ?? name]} /></PieChart></ResponsiveContainer>
      <div className="donut-total"><small>전체 운항</small><strong>{stats.total}<em>편</em></strong></div>
    </div><div className="stat-grid">{stats.breakdown.map(item => <div key={item.category}><span><i style={{ background: colors[item.category] }} />{statuses[item.category][0]}</span><strong>{item.count}<small>편</small></strong><small>{item.ratio.toFixed(1)}%</small></div>)}</div>
    <p className="panel-footnote">목록의 마스터 편 기준 · 시연 표본 통계</p>
  </Panel>;
}

