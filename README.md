# PV Viewer — Exercises for Agentic Coding Workshop

The notebook in this repo fetches archived (X)GMD and GDet data from the archive appliance and plots a single PV at a time. The `matplotlib` widget is interactive, allowing users to zoom, pan, reset axis limits, and save the plot. We will use coding agents to help us develop this notebook into a standalone **PyDM / PyQt application** that can be invoked through the LCLSHOME Launchpad.

## Background

LCLS produces X-ray pulses on two undulator lines:

| Line | Name | Photon energy range |
|------|------|---------------------|
| **HXR** | Hard X-Ray | ~2–25 keV |
| **SXR** | Soft X-Ray | ~0.25–2 keV |

Each line has gas-based detectors that measure **pulse energy** non-destructively (the beam passes through a low-pressure gas volume):

| PV | Detector | Beamline | Units |
|----|----------|----------|-------|
| `EM1K0:GMD:HPS:milliJoulesPerPulse` | Gas Monitor Detector | SXR | mJ |
| `EM2K0:XGMD:HPS:milliJoulesPerPulse` | X-ray Gas Monitor Detector | SXR | mJ |
| `GDET:FEE1:241:ENRC` | Gas Detector 241 (upstream) | HXR | mJ |
| `GDET:FEE1:361:ENRC` | Gas Detector 361 (downstream) | HXR | mJ |

All four report single-shot pulse energy in millijoules. 

## Environment setup
One goal of this assignment is to demonstrate the advantage of agents that can interact with the local filesystem through the shell. The PV archiver only accepts requests from certain hosts such as `lcls-srv01` and `dev-srv09`, so we will need to `ssh` onto `dev-srv09` and run the agents there. 

### Host (SSH)
To standardize the archiver behavior, you should run this notebook on `dev-srv09`.
```
ssh -J mcclogin dev-srv09
```
In VSCode, click "Connect to Host..." > "Add new SSH Host...", input `ssh -J mcclogin dev-srv09`

### Shell / environment variables
Once on `dev-srv09`, add the following to the bottom of your `.bashrc` and `source .bashrc`:

```
# Source the production environment into the current shell.
prodondev() {
  source /afs/slac/g/lcls/tools/script/ENVS64.bash
  source $EPICS_SETUP/envSet_prodOnDev.bash 
}

prodondev
```
You can rerun this step from the terminal at any time by running `prodondev`.
(For why this is necessary, see: https://confluence.slac.stanford.edu/spaces/ARD/pages/695784800/Prod-on-dev+setup)

### Python
After sourcing the prod-on-dev setup, locate the system Python executable using `which python`, then open `pv_viewer.ipynb` and select the system Python as the kernel.

Try running `pv_viewer.ipynb`, and you should see the interactive plot as the output of the last cell. If nothing shows up, the requested device was not recording data; try changing the index, e.g.
```
fig = plot_pv(list(PV_DEFS.keys())[3], hours_back=4.0)
```

> **Tip:** At some point you may need to instruct the agent (with either prompts or AGENTS.md) to run commands on the machine itself instead of in a sandbox, and you'll need to approve (or auto-approve) the terminal commands it wants to run.

### FastX
We will be building a GUI, so it will be nice to see the work in progress. If you don't already have FastX installed, follow these instructions: https://it.slac.stanford.edu/support/KB0012877#mcetoc_1i6g8b27k91. You may also use FastX in the browser instead of downloading it.

## Module 1: Copilot

### 1.1
Use Copilot to create a PyQT or PyDM wrapper around the interactive plotting logic in the notebook. 
Your solution should:
1. Display all 4 plots at once. *(Hint: use `matplotlib` subplots)*
2. Let the user select the time range to plot.
3. Have a *Refresh* button that re-fetches and redraws the data.
4. Preserve the interactive features of the widget: home (reset axes), forward/back, pan, zoom, save figure.

Use FastX to inspect the results and iterate.

> **Tip:** Start by asking the agent to read this notebook and explain what each piece does,
> then ask it to scaffold a PyDM `Display` (or a plain PyQt `QWidget`) around the same logic.

### (Optional) 1.2
If you quickly accomplish the above and have time to spare, you may try adding a few of these extra features:

> **Tip:** Adding these all at once may be more token-efficient, but incremental development makes things easier to debug when the agent gets something wrong. 

> **Tip:** _Test-driven development_ means every time you add a feature, you add a test to ensure you don't break that feature in the future. You can explicitly instruct the agent to add a test for each new feature, or (later) add a skill that describes TDD: https://agent-knowledge-hub.slac.stanford.edu/skills/tdd-standards 

1. When opened, have the viewer default to fetching and plotting the last 8 hours of data.
2. Allow the user to switch between viewing a single PV and all PVs on the canvas. 
3. Include hotkeys for the widget controls above. E.g. `z` to toggle zoom mode, `p` to toggle pan, `r` to reset, left and right arrow keys to go back or forward between views.
4. Add a nicer date/time picker, such as combo boxes or a selectable calendar overlay.
5. Experiment with pulling periods greater than 8 hours. Downsample long series to around 1000 data points to speed up plotting.
6. Add support for strings representing relative times, such as `now`, `-5m`, `-8h`, `-1d16h`

> **Tip:** You are free to use your own software design instincts to guide the agent, e.g., "make a class that represents
> the canvas and preserves the current axis limits as class variables." This can make it easier for both you and the agent to 
> understand and remember key features of the code for future development.

## Module 2: Claude Code

Let's add real-time plotting functionality to our application. We will switch backends from `matplotlib` to [PyQtGraph](https://www.pyqtgraph.org/), which supports real-time plotting natively. We will use Claude Code to port our GUI from one plotting backend to the other.

Your solution should:
1. Migrate the plotting plugin from matplotlib to PyQtGraph.
2. When the user inputs `now` for the end time and clicks the Refresh button:
   * Display a "Live Update" checkbox (checked by default). While it is checked, new data is pulled and appended to the plot.
   * Display a "Refresh interval" field and "OK" button that allows the user to set the refresh rate. Min: 1s.
   * The plot should adjust its x-limits and incorporate new data every refresh interval.
   * Optional: add a checkbox to set whether the start time is held fixed or rolls with the updating end time.

Claude Code will likely create _subagents_, starting with a **Plan** or **Explore** agent, as it works through this task. Notice what they're doing -- usually fetching and reading webpages (**Fetch**), running shell commands (**Bash**), or writing code (**Write**).

> **Tip:** If you get tired of approving shell commands every 20 seconds, Ctrl-C out of Claude Code and relaunch as `claude --dangerously-skip-permissions`

## Module 3: Modifying Agent Behavior

### 3.1 AGENTS.md

AGENTS.md saves AI agents from having to figure out the codebase from scratch at each invocation.

Prompt Claude Code to create an AGENTS.md for the repo:

```
Draft an AGENTS.md for this repository. Include:
- what this codebase does and its scientific context
- the key packages and their status
- units conventions used throughout
- the data directory structure and what each file contains
- commands to run the notebook and tests

After drafting, flag anything you are uncertain about that I should verify.
```

### 3.2 SKILLS.md

Suppose we're in the ACR and we need to quickly record a snapshot of pulse energies over some time span. We can ask an agent to do this on the fly: "Plot GMD over the last 2 hours" and have it spit out a PNG that we can upload to the ELOG.

Instead of making the agent figure out how to do this from scratch each time, we can define a skill (using both `.md` and `.py` files) that makes the behavior reproducible and easy to trigger.

#### Testing the skill

Once the skill files are created, verify the skill works end-to-end:

1. **Check skill discovery** — Run `/skills` in Claude Code to confirm your new skill appears in the list.

2. **Basic invocation** — Try prompts like:
   ```
   Plot GMD over the last 2 hours
   ```
   ```
   Show me GDET pulse energy for the last 30 minutes
   ```
   The agent should produce a PNG file without asking you how to fetch or plot data.

4. **Verify output** — Open the saved PNG and confirm:
   - The time axis matches the requested range
   - Axis labels and title are present
   - The file is saved in a predictable location (e.g., current directory or a specified output path)


## (Optional) Module 4: Advanced techniques — MCP Server for MEME

We have taught the model a specific skill, but the archiver itself can do much more, such as look up groups of PV names. We will use git worktrees to do two things in parallel: (1) create an MCP server for the [`meme`](https://github.com/slaclab/meme) package, and (2) add a feature to our GUI.

### Background: What is MEME?

[MEME](https://github.com/slaclab/meme) (MAD EPICS MATLAB Environment) is a Python wrapper for SLAC's accelerator services. It provides three sub-modules:

| Module | Purpose | Example |
|--------|---------|---------|
| `meme.archive` | Fetch archived PV history data | `meme.archive.get("GDET:FEE1:241:ENRC", from_time="1 hour ago", to_time="now")` |
| `meme.names` | Query the directory service for PV/device/element names | `meme.names.list_pvs("BPMS:%:%:TMIT", tag="L2", sort_by="z")` |
| `meme.model` | Get machine model data (R-matrices, Twiss parameters) | `Model("CU_HXR").get_rmat("BPMS:LI24:801")` |

Dependencies: `p4p`, `numpy`, `pandas`, `requests`, `dateparser`

### 4.1 Creating the MCP Server

The goal is to expose MEME's functionality as an MCP (Model Context Protocol) server so that Claude Code (or any MCP client) can call MEME tools directly — searching for PV names, fetching archive data, or querying the machine model without you writing boilerplate each time.

#### Step 1: Set up a worktree

```bash
git worktree add -b mcp-server .claude/worktrees/mcp-server
cd .claude/worktrees/mcp-server
```

Or in Claude Code:
```
Create a worktree called mcp-server and work there.
```

#### Step 2: Prompt Claude Code to scaffold the server

```
Create an MCP server that wraps the `meme` Python package (https://github.com/slaclab/meme).
The server should expose these tools:

1. **list_pvs** — Search for PV names using a pattern (Oracle wildcard or regex).
   Parameters: pattern (str, required), tag (str, optional), sort_by (str, optional)
   Wraps: meme.names.list_pvs()

2. **list_devices** — Search for device names using a pattern.
   Parameters: pattern (str, required), tag (str, optional), sort_by (str, optional)
   Wraps: meme.names.list_devices()

3. **get_archive_data** — Fetch historical PV data from the archiver.
   Parameters: pv (str or list, required), from_time (str, required), to_time (str, default "now")
   Wraps: meme.archive.get()

4. **get_archive_dataframe** — Fetch historical PV data as a pandas DataFrame (returned as JSON).
   Parameters: pv (str or list, required), from_time (str, required), to_time (str, default "now")
   Wraps: meme.archive.get_dataframe()

5. **get_rmat** — Get the R-matrix for a beamline element.
   Parameters: element (str, required), model_name (str, default "CU_HXR"), model_source (str, default "BMAD")
   Wraps: meme.model.Model().get_rmat()

6. **get_twiss** — Get Twiss parameters for a beamline element.
   Parameters: element (str, required), model_name (str, default "CU_HXR"), model_source (str, default "BMAD")
   Wraps: meme.model.Model().get_twiss()

Use the `mcp` Python SDK (pip install mcp) with the FastMCP pattern.
The server should run via stdio transport.
Include error handling that returns descriptive messages when MEME calls fail.
```

#### Step 3: Expected server structure

The agent should produce something like:

```
mcp_meme_server/
├── server.py          # FastMCP server with tool definitions
├── pyproject.toml     # Package metadata and dependencies
└── README.md          # Usage instructions
```

A minimal tool implementation looks like:

```python
from mcp.server.fastmcp import FastMCP
import meme.names
import meme.archive

mcp = FastMCP("meme")

@mcp.tool()
def list_pvs(pattern: str, tag: str | None = None, sort_by: str | None = None) -> list[str]:
    """Search the MEME directory service for PV names matching a pattern.
    
    Pattern uses Oracle-style wildcards (% as wildcard) or regex.
    Common tags: L1, L2, L3, BSY, LTU, UND, DUMPLINE.
    """
    return meme.names.list_pvs(pattern, tag=tag, sort_by=sort_by)
```

#### Step 4: Register the MCP server with Claude Code

Add the server to your Claude Code settings (`.claude/settings.json` or project-level):

```json
{
  "mcpServers": {
    "meme": {
      "command": "python",
      "args": ["mcp_meme_server/server.py"],
      "env": {}
    }
  }
}
```

Or use `uv` if you set up the server as a package:
```json
{
  "mcpServers": {
    "meme": {
      "command": "uv",
      "args": ["run", "--directory", "mcp_meme_server", "server.py"]
    }
  }
}
```

#### Step 5: Test the MCP server

1. **Verify server starts** — Run the server directly to check for import errors:
   ```bash
   python mcp_meme_server/server.py
   ```
   (It should block waiting for stdio input — Ctrl+C to exit.)

2. **Test via Claude Code** — Restart Claude Code, then try:
   ```
   Use the meme tools to find all BPM PVs in the LTU region, sorted by z position.
   ```
   Claude should call your `list_pvs` tool with `pattern="BPMS:%", tag="LTU", sort_by="z"`.

3. **Test archive retrieval:**
   ```
   Use meme to fetch GDET:FEE1:241:ENRC data from the last hour and summarize the statistics.
   ```

4. **Test error handling:**
   ```
   Use meme to fetch data for FAKE:PV:NAME from the last hour.
   ```
   Should return a helpful error message, not a traceback.

### 4.2 Adding a GUI feature (parallel work)

While the MCP server is being built in one worktree, use another worktree (or the main branch) to add a feature to the PV viewer GUI — for example, a PV search dialog that could eventually connect to the MCP server's `list_pvs` tool.

### Important notes

- **Network access**: The MEME services require PVAccess (p4p) network connectivity. The `meme.archive` module also supports HTTP mode via the LCLS archiver appliance (`lcls-archapp.slac.stanford.edu`). Run from `dev-srv09` or a host with PVA access.
- **Model paths**: Valid model paths are `CU_HXR`, `CU_SXR`, `CU_SPEC`, `SC_DIAG0`, `SC_BSYD`, `SC_HXR`, `SC_SXR`, `FACET2E`. FACET2E requires `model_source="LUCRETIA"`.
- **Time strings**: `meme.archive.get()` accepts human-readable strings like `"1 hour ago"`, `"now"`, `"2 days ago"` (parsed by `dateparser`), or Python `datetime` objects.
- **Wildcard syntax**: The names service uses `%` as the wildcard character (Oracle style), e.g., `BPMS:%:%:X`. It also accepts regex patterns like `(XCOR|BPMS):.*`.


https://i.programmerhumor.io/2026/05/5e33ce843c037cc9ea9535b9d45d740fd21d7b26bb71da9cc74df87608957149.png 