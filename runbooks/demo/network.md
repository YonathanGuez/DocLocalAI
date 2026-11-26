# Network Troubleshooting Reference

This runbook covers OpenShift SDN/OVN pod networking and route configuration.

## SDN/OVN Pod Connectivity Issues

Check the SDN pod logs for repeated connection resets. If the issue persists,
administrators may need to restart SDN/OVN pods to clear stale flow tables.

## Listing Routes

To list all routes exposed in the current project:

```bash
oc get routes
```

This returns the route host, path, and target service for every exposed route in
the namespace.
