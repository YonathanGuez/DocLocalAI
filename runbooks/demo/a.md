# Runbook A

Restart a pod by deleting it so the deployment controller recreates it automatically with a fresh container image pull, a clean filesystem, and reset in-memory state; this is the single most common first troubleshooting step across almost every pod-level incident, and it should always be tried before escalating to a full redeploy, a node drain and cordon, or a formal support ticket, because most transient pod issues resolve themselves the moment the pod is replaced and reinitializes cleanly from scratch.
