variable "slack_channel" {
  type        = string
  description = "Webhook URL for slack notifications"
}

variable "kms_arn" {
  type = string
}

variable "security_group_ids" {
  type = list(string)
}

variable "prefix" {
  type = string
}

variable "common_tags" {
  type = map(any)
}

variable "aws_region" {
  type = string
}

variable "aws_account_id" {
  type = string
}

variable "tags" {
  type    = map(any)
  default = {}
}

variable "private_subnet_ids" {
  type    = list(string)
  default = []
}


variable "sqs_worker_lambda_iam_role_arn" {
  type = string
}
variable "kms_key_id" {
  description = "If you don't provide kms_key_id the queue will not be encrypted"
  type        = string
  default     = null
}
