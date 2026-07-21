# Lambda container image — build target for AWS Lambda + Function URL
FROM public.ecr.aws/lambda/python:3.11
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt
COPY app ${LAMBDA_TASK_ROOT}/app
# Lambda handler = module.path.variable  ->  app/main.py, variable "handler"
CMD ["app.main.handler"]
