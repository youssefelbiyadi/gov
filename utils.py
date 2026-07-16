master_delete:
  extends: .test_base
  stage: master_delete
  needs:
    - "setup"
    - job: "master_create"
      optional: true
    - job: "master_refresh"
      optional: true
    - job: "client_create"
      optional: true
    - job: "client_delete"
      optional: true
  rules:
    - if: $MASTER_SUBSCRIPTION_OVERRIDE
      when: never
    - when: on_success
  script:
    - pytest -m master_delete --junitxml=reports/master_delete.xml
