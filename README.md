# PV Viewer — Exercises for Agentic Coding Workshop

The notebook in this repo fetches archived (X)GMD and GDet data from the archive appliance and plots a single PV at a time. The `matplotlib` widget is interactive, allowing users to zoom, pan, reset axis limits, and save the plot. We will use coding agents to help us develop this notebook into a standalone **PyDM / PyQt application** that can be invoked through the LCLSHOME Launchpad.

## Background

TODO: explain GMD, XGMD, GDET PVs, units, measure pulse energy, HXR vs. SXR

## Environment setup
One goal of this assignment is to demonstrate the advantage of agents that can interact with the local filesystem through the shell. The PV archiver only accepts requests from certain hosts such as `lcls-srv01` and `dev-srv09`, so we will need to `ssh` onto `dev-srv09` and run the agents there. 

To standardize the archiver behavior, you should run this notebook on `dev-srv09`.
```
ssh -J mcclogin dev-srv09
```
In VSCode, click "Connect to Host..." > "Add new SSH Host...", input `ssh -J mcclogin dev-srv09`

Once on `dev-srv09`, add the following to the bottom of your `.bashrc` and `source .bashrc`:

```
# Source the production environment into the current shell.
prodondev() {
  source /afs/slac/g/lcls/tools/script/ENVS64.bash
  source $EPICS_SETUP/envSet_prodOnDev.bash 
}

prodondev
```
You can rerun this step from the terminal at any time using 
(For why this is necessary, see: https://confluence.slac.stanford.edu/spaces/ARD/pages/695784800/Prod-on-dev+setup)

Locate the system Python executable using `which python`, then open `pv_viewer.ipynb` and select the system Python as the kernel.

Try running `pv_viewer.ipynb`, and you should see the interactive plot as the output of the last cell.

> **Tip:** You may need to instruct the agent (with either prompts or AGENTS.md) to run commands on the machine itself instead of in a sandbox, and you'll need to approve (or auto-approve) the terminal commands it wants to run.

## Module 1: Copilot

### 1.1
Use Copilot to create a PyQT or PyDM wrapper around the interactive plotting logic in the notebook. 
Your solution should:
1. Display all 4 plots at once. *(Hint: use `matplotlib` subplots)*
2. Let the user select the time range to plot.
3. Have a *Refresh* button that re-fetches and redraws the data.
4. Preserve the interactive features of the widget: home (reset axes), forward/back, pan, zoom, save figure.

Use FastX to 

> **Tip:** Start by asking the agent to read this notebook and explain what each piece does,
> then ask it to scaffold a PyDM `Display` (or a plain PyQt `QWidget`) around the same logic.

### (Optional) 1.2
If you quickly accomplish the above and have time to spare, you may try adding a few of these extra features:
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

Let's add real-time plotting functionality to our application. We will switch backends from `matplotlib` to (`PyQtGraph`)[https://www.pyqtgraph.org/], which supports real-time plotting natively. We will use Claude Code to port our GUI from one plotting backend to the other.

Your solution should:
1. Migrate the plotting plugin from matplotlib to PyQtGraph.
2. When the user inputs `now` for the end time and clicks the Refresh button:
   * Display a "Live Update" checkbox (checked by default). While it is checked, new data is pulled and appended to the plot.
   * Display a "Refresh interval" field and "OK" button that allows the user to set the refresh rate. Min: 1s.
   * The plot should adjust its x-limits and incorporate new data every refresh interval.
   * Optional: add a checkbox to set whether the start time is held fixed or rolls with the updating end time.

> **Tip:** Claude Code will likely create _subagents_, starting with a Plan agent. Notice what they're doing.

## Module 3: Modifying Agent Behavior

Say we're in the ACR and we need to quickly record a snapshot of pulse energies over some time span. We would like to be able to ask an agent to do this on the fly using a prompt like "Plot GMD over the last 2 hours" and have it spit out a PNG that we can upload to the ELOG.

Instead of making the agent figure out how to do this from scratch each time, we can define a skill (using both `.md` and `.py` files) that makes the behavior reproducible and easy to trigger.

### 3.1

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

### 3.2
Ask it to create the skill we described above, then test the skill. TODO: write tests for skill

## (Optional) Module 4: Advanced techniques
We have taught the model how to do a specific skill, but the archiver itself can do much more, such as look up groups of PV names. 

We will use git worktrees to do two things in parallel: (1) create an MCP server for the `meme` package, and (2) add a feature to our GUI.


