# Cdepsio6 Tool

![Pipe](gifs/blupipe.gif)

## Description

This tool can be used to modify the contents of the cell-dependent variables output file, **_cdepsout.bin_**, within an arbitrary number of user-specified cylinder regions. The user is able to explicitly set, skip, increment, scale or set new minimum and maximum values for any of the variables contained within this file. The tool can be accessed from the GUI using the "Tools"->"CFD++ Solution Tools"->"Solution File Modification"->"By Cylinders" command.

Once the command is invoked, the following panel will appear.

![cdepio5 tool](gifs/cdepsio6_1.gif)

If a previously defined tool input file, **_cdepsio6.inp_** exists in the current directory, the user can load this file using the "Read cdepsion6.inp File" button. Otherwise enter the number of subsets (cylinders) within which the variables in the **_cdepsout.bin_** file will be modified and click on "Proceed".

![cdepio5 tool](gifs/cdepsio6_2.gif)

The user can scroll through the subsets or cylinders using the buttons and arrows at the top right of this panel. The first set of radio buttons determines whether the cdepsout.bin file should be copied to cdepsin.bin file before the tool runs. The second set of radio buttons determines whether the cdepsout.bin file should be copied to cdepsin.bin file after the tool runs. The coordinates of the start and end points as well as the radius of the cylinder should be specified In the next section of the panel. In the entry box below the user should enter the number of variables to be modified and click on "Enter". In the last section of the panel, the user should enter a value for each variable and select the action to be performed with the variable. The options are to set a new value for the variable, to skip the variable, add to (or increment) the variable, to scale the variable, or to clip it with prescribed minimum or maximum values.

At the bottom of the panel there are three buttons. The "Read cdepsion6.inp File" button loads a previously defined tool input file in the current directory. The "Write and Run" button brings up a pull-down menu with three options: write and run, write only and run only. The "Close" button closes the panel without further action.

## Shell Command Usage

The tool is also available as a shell command.

The tool reads the default CFD++ cells and nodes files (usually **_cellsin.bin_** and **_nodesin.bin_**, unless these default names were altered within the **_mcfd.inp_** file) and an input ASCII file, named **_cdepsio6.inp_**. The format of this ASCII file is given below. Please note that variables are denoted with a dollar sign (its actual value must be substituted here) and the variable type is given in parentheses. The action can be one of the following: "add", "skip","scale", "min", or "max". If no action is specified, the "set" action will be taken.

```
nsubsets $nos(int)
subset 1
  x1 $val(float)
  y1 $val(float)
  z1 $val(float)
  x2 $val(float)
  y2 $val(float)
  z2 $val(float)
  radius $val(float)
  nvar $novars(int)
  q1 $q1(float) action
  q2 $q2(float) action
  .
  .
  .
  qn $qn(float) action
subset 2
  .
  .
  .
subset n
```

## Executable Name

**_cdepsio6_** or **_cdepsio6.exe_**

## Usage

**cdepsio6**

## Interactive Inputs

None.

## Sample Session Output

```
...
Processing subset #1
xmin = -1.0000000e-01, xmax =  3.1000000e+00
ymin = -1.0000000e-01, ymax =  1.0000000e-01
zmin = -1.0000000e-01, zmax =  1.0000000e-01
q1 =  1.0000000e+00, op = "set"
q2 =  2.0000000e+00, op = "skip"
q3 =  3.0000000e+00, op = "add"
q4 =  4.0000000e+00, op = "skip"
q5 =  5.0000000e+00, op = "scale"
q6 =  6.0000000e+00, op = "min"
Number of cells in subset#1 = 7500
gasc_l=3 in gasvini.c
mx_gas=3
visc_l=37500 in visvini.c
mx_vis=5
cdepsout.bin (restart file) created at nt=332, tau= 0.0000000e+00
...
```

## Status

This tool is available as a shell command and from the GUI.