# spin-software-ci

[![Sponsor](https://img.shields.io/badge/Sponsor-fitzyracing1-ea4aaa?logo=githubsponsors)](https://github.com/sponsors/fitzyracing1)
[![test](https://github.com/fitzyracing1/spin-software-ci/actions/workflows/test.yml/badge.svg)](https://github.com/fitzyracing1/spin-software-ci/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Read a GitHub Actions workflow or log and flag common failure causes by rules. Lit or dark: same input, same answer, no API, no cost, works offline.

The checker ships in a pull request. It will read a workflow YAML or a job log and print LIT or DARK with the rules that fired.

## Run it

It's plain Python 3 with no packages to install, so it runs anywhere Python does.

```sh
gh repo clone fitzyracing1/spin-software-ci
cd spin-software-ci
python software_ci.py
python -m pytest -q
```

### Windows (PowerShell)
```powershell
winget install Python.Python.3.12 GitHub.cli
gh auth login
gh repo clone fitzyracing1/spin-software-ci; cd spin-software-ci; py software_ci.py
```

### Mac
```sh
brew install python gh && gh auth login
gh repo clone fitzyracing1/spin-software-ci && cd spin-software-ci && python3 software_ci.py
```

### Linux
```sh
sudo apt install -y python3 gh && gh auth login
gh repo clone fitzyracing1/spin-software-ci && cd spin-software-ci && python3 software_ci.py
```

### Termux (Android)
```sh
pkg install -y python git gh && gh auth login
gh repo clone fitzyracing1/spin-software-ci ~/spin-software-ci && cd ~/spin-software-ci && python software_ci.py
```

## Support this project

spin-software-ci is free and MIT licensed. If it saves you time, please [sponsor me on GitHub](https://github.com/sponsors/fitzyracing1). It keeps the tools coming.

| Plan | Price | What you get |
| --- | --- | --- |
| Free | $0 | Everything in this repo, forever |
| Pro | $49/month | Priority issues and help adding your own tools |
| Team | $199/month | Custom tools built for your team, plus Pro |

Plans are paid through [GitHub Sponsors](https://github.com/sponsors/fitzyracing1). You can also star the repo, share it, or open an issue with a tool idea.

## Author

Built by Joshua Almeida ([@fitzyracing1](https://x.com/fitzyracing1), [fitzyracing1.com](https://fitzyracing1.com), [GitHub](https://github.com/fitzyracing1)).

## License

[MIT](LICENSE) © 2026 Joshua Almeida
