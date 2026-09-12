# SG-Gateway 23.01 — GitHub commands

Development channel: `dev-02301`.

## Clean install

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/dev-02301/deploy/install-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=dev-02301 bash
```

## Update

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/dev-02301/deploy/update-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=dev-02301 bash
```

## Full uninstall

```bash
curl -4 -fsSL https://raw.githubusercontent.com/s-gor/sg-gateway-v23/dev-02301/deploy/uninstall-from-github.sh | sudo env SG_GATEWAY_GITHUB_BRANCH=dev-02301 bash
```
