Provider addons consume this layer through component names, `usage`, and
`work_on(...)` lookups.

Transport-specific addons should hand normalized inbound work into the inbound
listener and leave provider-specific routing and mapping in provider addons.
