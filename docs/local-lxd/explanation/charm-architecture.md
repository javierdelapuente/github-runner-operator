# Charm architecture

Conceptually, the charm can be divided into the following:

- Management of LXD ephemeral virtual machines to host [ephemeral self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/autoscaling-with-self-hosted-runners#using-ephemeral-runners-for-autoscaling)
- Management of the virtual machine image
- Management of the network
- GitHub API usage
- Management of [Python web service for checking GitHub repository settings](https://github.com/canonical/repo-policy-compliance)
- Management of dependencies

## LXD ephemeral virtual machines

To ensure a clean and isolated environment for every runner, self-hosted runners use LXD virtual machines. The charm spawns virtual machines, setting resources based on charm configurations. The self-hosted runners start with the ephemeral option and will clean themselves up once the execution has finished, freeing the resources. This is similar to [how GitHub hosts their runners due to security concerns](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners#self-hosted-runner-security).

As the virtual machines are single-use, the charm will replenish virtual machines on a regular schedule. This time period is determined by the [`reconcile-interval` configuration](https://charmhub.io/github-runner/configure#reconcile-interval).

On schedule or upon configuration change, the charm performs a reconcile to ensure the number of runners managed by the charm matches the [`virtual-machines` configuration](https://charmhub.io/github-runner/configure#virtual-machines), and the resources used by the runners match the various resource configurations.

To prevent disk IO exhaustion on the Juju machine on disk-intensive GitHub workflows, the charm has two storage options provided by [`runner-storage` configuration](https://charmhub.io/github-runner/configure#runner-storage):

- Use memory of the Juju machine as disk. Under this option, the [`vm-disk` configuration](https://charmhub.io/github-runner/configure#vm-disk) can impact the memory usage of the Juju machine.
- Use storage mount by Juju as the disk.

## Virtual machine image

The virtual machine images are built on installation and on a schedule every 6 hours. These images are constructed by launching a virtual machine instance, modifying the instance with configurations and software installs, and then exporting the instance as an image. This process reduces the time needed to launch a virtual machine instance for hosting the self-hosted runner application.

The software installed in the image includes:

- APT packages:
  - `docker.io`
  - `npm`
  - `python3-pip`
  - `shellcheck`
  - `jq`
  - `wget`
- npm packages:
  - `yarn`
- Binary downloaded:
  - `yq`

The configurations applied in the image include:
<!-- vale Canonical.005-Industry-product-names = NO -->
- Creating a group named `microk8s`.
- Adding the `ubuntu` user to the `microk8s` group. Note that the `microk8s` package is not installed in the image; this preconfigures the group for users who install the package.
- Adding the `ubuntu` user to the `docker` group.
- Adding iptables rules to accept traffic for the DOCKER-USER chain. This resolves a networking conflict with LXD.
<!-- vale Canonical.005-Industry-product-names = YES -->


## Network configuration

The charm respects the HTTP(S) proxy configuration of the model configuration of Juju. The configuration can be set with [`juju model-config`](https://juju.is/docs/juju/juju-model-config) using the following keys: `juju-http-proxy`, `juju-https-proxy`, `juju-no-proxy`. 
The GitHub self-hosted runner applications will be configured to utilize the proxy configuration. 
This involves setting environment variables such as `http_proxy`, `https_proxy`, `no_proxy`, `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY`
in various locations within the runner environment, such as `/etc/environment`.

However, employing this approach with environment variables has its drawbacks. 
Not all applications within a workflow may adhere to these variables as they 
[lack standardization](https://about.gitlab.com/blog/2021/01/27/we-need-to-talk-no-proxy/). 
This inconsistency can result in failed workflows, prompting the introduction of aproxy, as detailed in the subsection below.

### aproxy
If the proxy configuration is utilized and [aproxy](https://github.com/canonical/aproxy) is specified through the charm's configuration option,
all HTTP(S) requests to standard ports (80, 443, 11371) within the GitHub workflow will be automatically directed 
to the specified HTTP(s) proxy. Network traffic destined for ports 80 and 443 is redirected to aproxy using iptables.
aproxy then forwards received packets to the designated HTTP(S) proxy. 
Beyond that, the environment variables (`http_proxy`, `https_proxy`, `no_proxy`, `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`)
will no longer be defined  in the runner environment. 
It's worth noting that this setup deviates from the behavior when not using aproxy, 
where these variables are set in the runner environment. In that scenario, traffic to non-standard ports 
would also be directed to the HTTP(s) proxy, unlike when using aproxy.

### denylist

The nftables on the Juju machine are configured to deny traffic from the runner virtual machine to IPs on the [`denylist` configuration](https://charmhub.io/github-runner/configure#denylist). The runner will always have access to essential services such as DHCP and DNS, regardless of the denylist configuration.

## GitHub API usage

The charm requires a GitHub personal access token for the [`token` configuration](https://charmhub.io/github-runner/configure#token). This token is used for:

- Requesting self-hosted runner registration tokens
- Requesting a list of runner applications
- Requesting a list of self-hosted runners configured in an organization or repository
- Deleting self-hosted runners

The token is also passed to [repo-policy-compliance](https://github.com/canonical/repo-policy-compliance) to access GitHub API for the service.

Note that the GitHub API uses a [rate-limiting mechanism](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api?apiVersion=2022-11-28). When this limit is reached, the charm may not be able to perform the necessary operations and may go into
BlockedStatus. The charm will automatically recover from this state once the rate limit is reset, but using a different token with a higher rate limit may be a better solution depending on your deployment requirements.

## GitHub repository setting check

The [repo-policy-compliance](https://github.com/canonical/repo-policy-compliance) is a [Flask application](https://flask.palletsprojects.com/) hosted on [Gunicorn](https://gunicorn.org/) that provides a RESTful HTTP API to check the settings of GitHub repositories. This ensures the GitHub repository settings do not allow the execution of code not reviewed by maintainers on the self-hosted runners.

Using the [pre-job script](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/running-scripts-before-or-after-a-job#about-pre--and-post-job-scripts), the self-hosted runners call the Python web service to check if the GitHub repository settings for the job are compliant. If not compliant, it will output an error message and force stop the runner to prevent code from being executed.

## Dependencies management

Upon installing or upgrading the charm, the kernel will be upgraded, and the Juju machine will be restarted if needed.

The charm installs the following dependencies:

- For running repo-policy-compliance
  - gunicorn
- For firewall to prevent runners from accessing web service on the denylist
  - nftables
- For virtualization and virtual machine management
  - lxd
  - cpu-checker
  - libvirt-clients
  - libvirt-daemon-driver-qemu
  - apparmor-utils

These dependencies can be regularly updated using the [`landscape-client` charm](https://charmhub.io/landscape-client).

The charm installs the following dependencies and regularly updates them:

- repo-policy-compliance
- GitHub self-hosted runner application

The charm checks if the installed versions are the latest and performs upgrades if needed before creating new virtual machines for runners.

## COS Integration
Upon integration through the `cos-agent`, the charm initiates the logging of specific metric events
into the file `/var/log/github-runner-metrics.log`. For comprehensive details, please refer to the
pertinent [specification](https://discourse.charmhub.io/t/specification-isd075-github-runner-cos-integration/12084).

Subsequently, the `grafana-agent` transmits this log file to Loki, facilitating access for Grafana's visualization capabilities.
Notably, most events are transmitted during reconciliation. This approach prioritizes long-term monitoring over real-time updates, aligning with the intended monitoring objectives.