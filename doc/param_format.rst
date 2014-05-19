=====================
Parameter file format
=====================

``mqrun`` parameter files can be json or yaml formatted. To keep this
tutorial easy to read we will only use yaml files. Just replace all
yaml file endings by ``.json`` and use the standard library json
module to load the data if you want to use json instead.

``mqrun`` parameter files must contain the sections ``rawFiles``,
``fastaFiles`` and ``globalParams``. The sections ``topLevelParams``
(will probably move to ``globalParams`` soon) and ``MSMSParams`` are
optional.

The sections ``globalParams``, ``topLevelParams``,
``MSMSParams`` and the ``params`` subsection of ``rawFiles`` must
contain a ``defaults`` value. This will set default values for all
other parameters in this section. The output of ``mqrun`` includes a
file with all parameters explicitly set so you can see what values
have been used.

Global parameters
-----------------

This section corresponds to the ``global`` tab in the MaxQuant GUI and
includes parameters that are not specific to a particular input file.
For example

.. code:: yaml

   globalParams:
     defaults: default
     equalIl: true
     matchBetweenRuns: true
     fixedModifications:
       - "Carbamidomethyl (C)"

Raw file section
----------------

The parameter files do not include paths to raw data, instead each
input file is specified by a name and corresponding parameters. When
``mqrun`` is called, it expects a mapping from input file names to
actual file paths. This way the same configuration can be used for
different data sets and on different computers without changing the
parameter file.

In theory each input file could use a different set of file specific
parameters, but usually a large number of input files share their
configuration. Theses groups of input files correspond to the
parameter groups in the MaxQuant GUI. The section ``rawFiles`` is
a list of these groups.

Each group has two sections of its own: ``files``, a list of names,
fractions and experiments, and a parameter section ``params``.

A configuration with two parameter groups could look like this:

.. code:: yaml

   rawFiles:
   - files:
       - name: 20090812_SvNa_SA_phospho_2_p1
         fraction: 1
       - name: 20090812_SvNa_SA_phospho_2_p2
         fraction: 2
       - name: 20090812_SvNa_SA_phospho_2_p7
         fraction: 3
       - name: 20090812_SvNa_SA_phospho_2_p8
         fraction: 4
     params:
       defaults: default
       intensityDependentCalibration: true
       isotopeTimeCorrelation: 0.8
       centroidMatchTol: 10
       isotopeMatchTol: 3
       mainSearchTol: 7.5
       variableModifications:
         - "Acetyl (Protein N-term)"
         - "Oxidation (M)"
         - "Phospho (STY)"
       useMs1Centroids: true
       matchType: "NoMatching"
       multiplicity: 2
       maxLabeledAa: 3
       labelMods:
         - ["Arg6", "Lys8"]
         - ["Arg10", "Lys8"]
   - files:
       - name: 20090812_SvNa_SA_phospho_2_FT1
         fraction: 5
       - name: 20090812_SvNa_SA_phospho_2_FT2
         fraction: 6
       - name: 20090812_SvNa_SA_phospho_2_FT3
         fraction: 7
       - name: 20090812_SvNa_SA_phospho_2_7
         fraction: 8
       - name: 20090812_SvNa_SA_phospho_2_8
         fraction: 9
       - name: 20090812_SvNa_SA_phospho_2_9
         fraction: 10
       - name: 20090812_StPe_SA_phospho_2_10
         fraction: 11
     params:
       defaults: default
       intensityDependentCalibration: true
       isotopeTimeCorrelation: 0.8
       centroidMatchTol: 10
       isotopeMatchTol: 3
       mainSearchTol: 7.5
       variableModifications:
         - "Acetyl (Protein N-term)"
         - "Oxidation (M)"
         - "Phospho (STY)"
       useMs1Centroids: true
       matchType: "NoMatching"
       multiplicity: 2
       maxLabeledAa: 3
       labelMods:
         - ["Arg6", "Lys8"]
         - ["Arg10", "Lys8"]


Fasta files
-----------

The fasta files are specified in the ``fastaFiles`` section. It must
include two subsections, ``fileNames`` and ``firstSearch``. The as
with the raw files the actual file paths are set when ``mqrun`` is
executed.

An example:

.. code:: yaml

  fileNames:
    - uniprot_sprot
  firstSearch: []

