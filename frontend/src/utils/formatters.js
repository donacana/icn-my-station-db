export const time = value => new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(value));
export const date = value => new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'short' }).format(new Date(value));
export const number = value => new Intl.NumberFormat('ko-KR').format(value);
export const windLabel = degree => ['북', '북동', '동', '남동', '남', '남서', '서', '북서'][Math.round(degree / 45) % 8];
export const statuses = {
  SCHEDULED: ['정상', 'green'], NORMAL: ['정상', 'green'], BOARDING: ['탑승중', 'blue'],
  BOARDING_SOON: ['탑승준비', 'orange'], DELAYED: ['지연', 'red'], CANCELLED: ['결항', 'gray'],
  DIVERTED: ['회항', 'purple'], DEPARTED: ['출발', 'blue'], ARRIVED: ['도착', 'green'],
  LOW: ['원활', 'green'], MID: ['보통', 'orange'], HIGH: ['혼잡', 'red'],
};

