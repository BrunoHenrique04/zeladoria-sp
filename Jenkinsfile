// Pipeline DevSecOps da Zeladoria SP
// GitHub -> Testes -> SonarQube -> Quality Gate -> Docker Build -> Trivy -> Docker Hub -> Deploy -> Validação
//
// As ferramentas rodam em containers efêmeros pelo Docker do host. O workspace do Jenkins
// fica no mesmo caminho dentro e fora do container (/var/jenkins_home), por isso os
// bind mounts com $WORKSPACE funcionam.

pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 30, unit: 'MINUTES')
    }

    triggers {
        githubPush()
    }

    environment {
        IMAGE          = "${env.DOCKERHUB_REPO ?: 'androww/zeladoria-sp'}"
        PYTHON_IMAGE   = 'python:3.12-slim'
        SCANNER_IMAGE  = 'sonarsource/sonar-scanner-cli:12.3'
        TRIVY_IMAGE    = 'aquasec/trivy:0.76.1'
        CI_NETWORK     = 'devsecops'
        APP_URL        = 'http://host.docker.internal:8000'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.SHORT_SHA = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                    env.TAG = "${env.BUILD_NUMBER}-${env.SHORT_SHA}"
                    currentBuild.displayName = "#${env.BUILD_NUMBER} ${env.SHORT_SHA}"
                }
                sh 'git log -1 --pretty="Commit %h por %an: %s"'
            }
        }

        stage('Testes') {
            steps {
                sh '''
                    docker run --rm \
                      -u "$(id -u):$(id -g)" -e HOME=/tmp \
                      -v "$WORKSPACE:/src" -w /src \
                      "$PYTHON_IMAGE" sh -c '
                        pip install -q --user -r requirements-dev.txt &&
                        python -m ruff check . &&
                        python -m pytest --cov --cov-report=xml:coverage.xml \
                          --cov-report=term --junitxml=test-results.xml'
                '''
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'test-results.xml'
                }
            }
        }

        stage('Análise SonarQube') {
            steps {
                withSonarQubeEnv('sonarqube') {
                    sh '''
                        docker run --rm --network "$CI_NETWORK" \
                          -u "$(id -u):$(id -g)" -e SONAR_USER_HOME=/tmp/.sonar \
                          -e SONAR_HOST_URL -e SONAR_TOKEN="$SONAR_AUTH_TOKEN" \
                          -v "$WORKSPACE:$WORKSPACE" -w "$WORKSPACE" \
                          "$SCANNER_IMAGE" \
                          -Dsonar.projectVersion="$TAG" -Dsonar.working.directory=$WORKSPACE/.scannerwork
                    '''
                }
            }
        }

        stage('Quality Gate') {
            steps {
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Docker Build') {
            steps {
                sh '''
                    docker build --pull \
                      --build-arg APP_VERSION="$TAG" \
                      -t "$IMAGE:$TAG" -t "$IMAGE:latest" .
                '''
            }
        }

        stage('Análise Trivy') {
            steps {
                // 1) Relatório completo (tabela no log, JSON, HTML e SBOM CycloneDX)
                sh '''
                    mkdir -p reports
                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      -v trivy-cache:/root/.cache/trivy \
                      -v "$WORKSPACE/reports:/reports" \
                      --entrypoint sh "$TRIVY_IMAGE" -c "
                        trivy image --no-progress --list-all-pkgs --format json -o /reports/trivy.json $IMAGE:$TAG &&
                        trivy convert --format table --severity HIGH,CRITICAL /reports/trivy.json &&
                        trivy convert --format template --template @/contrib/html.tpl -o /reports/trivy.html /reports/trivy.json &&
                        trivy convert --format cyclonedx -o /reports/sbom.cdx.json /reports/trivy.json;
                        status=\\$?; chown -R $(id -u):$(id -g) /reports; exit \\$status"
                '''
                // 2) Bloqueio: qualquer CRITICAL que já tenha correção publicada derruba o build
                sh '''
                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      -v trivy-cache:/root/.cache/trivy \
                      "$TRIVY_IMAGE" image --no-progress --skip-db-update \
                      --severity CRITICAL --ignore-unfixed --exit-code 1 \
                      "$IMAGE:$TAG"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true, fingerprint: true
                    publishHTML(target: [
                        reportDir: 'reports', reportFiles: 'trivy.html', reportName: 'Relatório Trivy',
                        keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true
                    ])
                }
            }
        }

        stage('Publicação da imagem') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub',
                                                  usernameVariable: 'DH_USER',
                                                  passwordVariable: 'DH_TOKEN')]) {
                    sh '''
                        echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
                        docker push "$IMAGE:$TAG"
                        docker push "$IMAGE:latest"
                        docker logout
                    '''
                }
            }
        }

        stage('Deploy') {
            steps {
                withCredentials([string(credentialsId: 'app-db-password', variable: 'APP_DB_PASSWORD')]) {
                    sh 'chmod +x scripts/*.sh && IMAGE_REF="$IMAGE:$TAG" DEPLOY_STATE_DIR=/var/jenkins_home/deploy-state scripts/deploy.sh'
                }
            }
        }

        stage('Validação funcional') {
            steps {
                sh 'scripts/smoke-test.sh "$APP_URL" "$TAG"'
            }
            post {
                failure {
                    withCredentials([string(credentialsId: 'app-db-password', variable: 'APP_DB_PASSWORD')]) {
                        sh 'DEPLOY_STATE_DIR=/var/jenkins_home/deploy-state scripts/rollback.sh'
                    }
                }
            }
        }
    }

    post {
        success {
            echo "Versão ${env.TAG} publicada em ${env.IMAGE} e no ar."
        }
        failure {
            echo 'Pipeline bloqueada. Veja o primeiro estágio em vermelho e o log dele.'
        }
        always {
            sh 'docker image prune -f --filter "until=72h" || true'
        }
    }
}
