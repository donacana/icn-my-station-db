import { dashboardMock } from '../mocks/dashboardMock.js';

export async function getDashboardData() {
  // API 연결 시 docs/api-contract.md 및 생성 타입을 확인하고 이 경계를 교체합니다.
  // 현재 네트워크 요청 없이 고정 시연 데이터만 반환합니다.
  return structuredClone(dashboardMock);
}

