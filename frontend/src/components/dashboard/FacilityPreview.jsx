import { useState } from 'react';
import { Coffee, Armchair, Pill, ShoppingBag, MapPin, Info } from 'lucide-react';
import Panel from '../common/Panel.jsx';
const categories = [['all', '전체'], ['LOUNGE', '라운지'], ['FOOD_CAFE', '식당·카페'], ['PHARMACY', '약국'], ['SHOPPING', '쇼핑'], ['ETC', '기타']];
const icons = { LOUNGE: Armchair, FOOD_CAFE: Coffee, PHARMACY: Pill, SHOPPING: ShoppingBag, ETC: Info };
export default function FacilityPreview({ facilities }) {
  const [category, setCategory] = useState('all');
  const rows = facilities.filter(item => category === 'all' || item.category === category);
  return <Panel title="편의시설" icon={Coffee}>
    <div className="facility-tabs">{categories.map(([id, label]) => <button key={id} aria-pressed={category === id} onClick={() => setCategory(id)}>{label}</button>)}</div>
    <div className="facility-list">{rows.map(item => {
      const Icon = icons[item.category];
      return <article className="facility-item" key={item.facilityId}><span className="facility-icon"><Icon size={18} /></span><div><h3>{item.name}<span className={item.isOpen ? 'open-label' : 'closed-label'}>{item.isOpen ? '영업중' : '영업종료'}</span></h3><p><MapPin size={11} />{item.terminal} · {item.floor} · {item.location}</p><small>{item.is24h ? '24시간' : `${item.openTime}–${item.closeTime}`}</small></div></article>;
    })}</div><p className="panel-footnote">시설·영업 상태는 시연 기준 예시입니다.</p>
  </Panel>;
}

