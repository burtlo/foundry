When I run `foundry up`

```
workspace=/Users/lynnfrank/src/foundry ready=True
bridge ok=True url=http://127.0.0.1:8791/v1/agent
host process ok=True pid=20010
host health ok=True detail=health RPC ok
adapter ok=True configured=True reachable=True
```

It's all very accurate but could use more user-focused formatting:

what is the ready=True, ok=True mean for the user?
What is a bridge?
process and health are useful information?
What is the adapter?

The user wants to know that foundry is up and that everything is healthy but
the information could be presented less like variables and internal services