import { ArrowLeft, Construction } from 'lucide-react';
export default function DetailPage({ title, onHome }) {
  return <main className="detail-page"><span className="detail-icon"><Construction size={35} /></span><span className="eyebrow">COMING NEXT</span><h1>{title}</h1><p>상세 화면을 준비하고 있습니다.</p><p>현재 프로토타입에서는 홈 대시보드에서 시연 정보를 확인할 수 있습니다.</p><button className="primary-button" onClick={onHome}><ArrowLeft size={17} />홈 대시보드로 돌아가기</button></main>;
}

