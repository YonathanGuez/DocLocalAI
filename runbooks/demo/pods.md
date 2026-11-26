# Pod Lifecycle & Troubleshooting

This runbook covers pod lifecycle, restarts, and troubleshooting for OpenShift pods.

## Listing Pods

To list all pods in the current project:

```bash
oc get pods
```

## Restarting a Pod

Restart a pod with kubectl delete pod.

## Pod Restarts

Restart a pod by deleting it.

```bash
kubectl delete pod my-pod
```

## Container Restart Loop

A container restart loop usually indicates a crash immediately after startup;
check `oc logs <pod> --previous` for the exact failure.
