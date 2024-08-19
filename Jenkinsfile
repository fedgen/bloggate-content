pipeline {
  agent any
  stages {
    stage('Checkout') {
      agent any
      steps {
        git(url: 'https://github.com/Akandeav/phis-content', branch: 'master', credentialsId: 'git-jenkins-tk')
      }
    }

    stage('Log') {
      parallel {
        stage('Log') {
          steps {
            sh 'ls -la'
          }
        }

        stage('Build') {
          steps {
            sh 'sudo docker build -t fedgen/content:1.0.1 .'
          }
        }

      }
    }

    stage('cleanup') {
      steps {
        sh 'sudo kubectl delete deploy/content-service-mongo'
      }
    }

    stage('deploy') {
      steps {
        sh 'sudo kubectl apply -f content-service.yaml'
      }
    }

    stage('verify-deploy') {
      steps {
        sh 'sudo kubectl get pods'
      }
    }

  }
}