master_create:
  extends: .test_base
  stage: master_create
  needs:
    - job: setup
    - job: dsource_onboard
      optional: true
      artifacts: true
  variables:
    DSOURCE_NAME: $DSOURCE_NAME_OVERRIDE
  rules:
    - if: $MASTER_SUBSCRIPTION_OVERRIDE
      when: never
    - when: on_success
  script:
    - pytest -m master_create --junitxml=reports/master_create.xml

master_refresh:
  extends: .test_base
  stage: master_refresh
  needs:
    - job: setup
    - job: master_create
      optional: true
      artifacts: true
  rules:
    - if: $MASTER_SUBSCRIPTION_OVERRIDE
      when: never
    - when: on_success
  script:
    - pytest -m master_refresh --junitxml=reports/master_refresh.xml

client_create:
  extends: .test_base
  stage: client_create
  needs:
    - job: setup
    - job: master_refresh
      optional: true
      artifacts: true
  variables:
    MASTER_SUBSCRIPTION_ID: $MASTER_SUBSCRIPTION_OVERRIDE
  script:
    - pytest -m client_create --junitxml=reports/client_create.xml
