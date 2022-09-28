# Design

Design documents for dev-tools. This was original created for Vault Health, but the code has been sanitized and made public for educational purposes.

## Param store

The basic design of the `param-store` set of commands is that objects are added to an S3 bucket, which triggers notification rules. The notification rules pipe messages into one of two SQS queue based the key prefix: `requested/`, `accepted/`, or `rejected/` go into the notification queue, while `review/`, goes into the review queue.

![Architecture Diagram](assets/param-store-cli-bg.svg)

There are two commands for now: `request` and `review`. A successful `request` creates an S3 object with a key prefixed by `requested/`. The notifier lambda will move these object to the same key, but replacing the prefix with `review/`.

There is no lambda that processes the review queue; instead, that queue is consumed by the `review` command. A successful review will, depending on reviewer input, move the object to the same key, but replacing the prefix with `accepted/` or `rejected/` as appropriate. If the `review` command errors or the reviewer chooses not to approve or accept, the object will be moved back to the same key, but replacing the `review/` prefix with `requested/` so it can be reviewed again later.
