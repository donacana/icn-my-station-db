pipeline {
    agent { label 'icn-ci' }
    options {
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
        timeout(time: 20, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timestamps()
    }
    triggers { pollSCM('H/5 * * * *') }
    stages {
        stage('Checkout') {
            steps {
                deleteDir()
                checkout scm
            }
        }
        stage('Backend dependencies') {
            steps {
                dir('backend') {
                    sh 'uv sync --locked --group dev'
                }
            }
        }
        stage('Backend tests') {
            steps {
                script {
                    def result = sh(
                        script: 'cd backend && uv run --frozen pytest --junitxml=pytest-results.xml',
                        returnStatus: true
                    )
                    if (fileExists('backend/pytest-results.xml')) {
                        junit testResults: 'backend/pytest-results.xml', allowEmptyResults: true
                    }
                    if (result == 5) {
                        unstable('pytest 테스트가 없습니다. GitHub 연결만 확인되었으며 배포 준비 완료가 아닙니다.')
                    } else if (result != 0) {
                        error("pytest 실패 (exit ${result}). 배포할 수 없습니다.")
                    }
                }
            }
        }
    }
    post {
        always {
            echo '이 파이프라인은 CI 전용입니다. RDS 마이그레이션 및 앱 배포는 실행하지 않습니다.'
            deleteDir()
        }
    }
}
