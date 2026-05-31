# PV Viewer — Exercises for Agentic Coding Workshop

The notebook in this repo fetches archived (X)GMD and GDet data from the archive appliance and plots a single PV at a time. The `matplotlib` widget is interactive, allowing users to zoom, pan, reset axis limits, and save the plot. We will use coding agents to help us develop this notebook into a standalone **PyDM / PyQt application** that can be invoked through the LCLSHOME Launchpad.

## Environment setup
One goal of this assignment is to demonstrate the advantage of local agents over cloud execution or copy/pasting code when working in specialized environments. This notebook queries the PV archiver, which only accepts requests from certain hosts. You may need to *tell* the agent (with either prompts or AGENTS.md) to run commands on the machine itself instead of a sandbox, and you'll need to approve (or auto-approve) the terminal commands it wants to run.

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


## Module 1: Copilot

### 1.1
Use Copilot to create a PyQT or PyDM wrapper around the interactive plotting logic in the notebook. 

Your solution should:
1. Display all 4 plots at once. *(Hint: use `matplotlib` subplots)*
2. Let the user select the time range to plot.
3. Have a *Refresh* button that re-fetches and redraws the data.
4. Preserve the interactive features of the widget: home (reset axes), forward/back, pan, zoom, save figure.

> **Tip:** Start by asking the agent to read this notebook and explain what each piece does,
> then ask it to scaffold a PyDM `Display` (or a plain PyQt `QWidget`) around the same logic.

### (Optional) 1.2
If you quickly accomplish the above and have time to spare, you may try a few of these optional/"stretch" goals:
1. When opened, have the viewer default to fetching and plotting the last 8 hours of data.
2. Allow the user to switch between viewing a single PV and all PVs on the canvas. 
3. Include hotkeys for the widget controls above. E.g. `z` to toggle zoom mode, `p` to toggle pan, `r` to reset, left and right arrow keys to go back or forward between views.
4. Add a nicer date/time picker, such as combo boxes or a selectable calendar overlay.
5. Experiment with pulling periods greater than 8 hours. Downsample long series to around 1000 data points to speed up plotting.
6. Add support for strings representing relative times, such as `now`, `-8h`, `-1d16h`, `last owl shift`.

> **Tip:** You are free to use your own software design instincts to guide the agent, e.g., "make a class that represents
> the canvas and preserves the current axis limits as class variables." This can make it easier for both you and the agent to 
> understand and remember key features of the code for future development.

## Module 2: Claude Code

Let's add real-time functionality to our plotting application. We will switch backends from `matplotlib` to (`PyQtGraph`)[https://www.pyqtgraph.org/], which supports real-time plotting natively. We will use Claude Code to port our GUI from one plotting backend to the other.

Your solution should:
1. Update the data displayed every 10 seconds

> **Tip:** Claude Code will likely create _subagents_, starting with a Plan agent. Notice what they're doing.

## Module 3: Skills and AGENTS.md
Let's say we're in the ACR and we need to quickly record a
