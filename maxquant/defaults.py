    

yaml_strings = dict(default_tripleSILAC='''
fasta-files:
  - uniprot_coli_K12-MG1655_complete-canonical_20110909LP.fasta
                    
restrict-mods:
  - Oxidation (M)
  - Acetyl (Protein N-term)

default-group:
  top-level-parameters:
    maxCharge: 7
    lcmsRunType: 0
    msInstrument: 0
    groupIndex: 1
    maxLabeledAa: 3
    maxNmods: 5
    maxMissedCleavages: 2
    multiplicity: 3
    protease: Trypsin/P
    proteaseFirstSearch: Trypsin/P
    useProteaseFirstSearch: false
    useVariableModificationsFirstSearch: false
    hasAdditionalVariableModifications: false
    doMassFiltering: true
    firstSearchTol: 20
    mainSearchTol: 6
    
  variableModifications:
    - Oxidation (M)
    - Acetyl (Protein N-term)

  variableModificationsFirstSearch:
    - Oxidation (M)
    - Acetyl (Protein N-term)                   
                    
  isobaricLabels:
    - iTRAQ4plex-Nter114
    - iTRAQ4plex-Nter115
    - iTRAQ4plex-Nter116
    - iTRAQ4plex-Nter117
    - iTRAQ4plex-Lys114
    - iTRAQ4plex-Lys115
    - iTRAQ4plex-Lys116
    - iTRAQ4plex-Lys117
  labels:
    - {0}
    - {1}
    - {2}
  
msms-parameters:
  default:
    InPpm: true
    Deisotope: true
    Topx: 10
    HigherCharges: true
    IncludeWater: true
    IncludeAmmonia: true
    DependentLosses: true
  fragment-spectrum-settings:
    FTMS:
      Tolerance:
        Value: 20
        Unit: Ppm
    ITMS:
      InPpm: false
      Deisotope: false
      Topx: 6
      Tolerance:
        Value: 0.5
        Unit: Dalton
    TOF:
      InPpm: false
      Tolerance:
        Value: 0.1
        Unit: Dalton
    Unknown:
      InPpm: false
      Deisotope: false
      Topx: 6
      Tolerance:
        Value: 0.5
        Unit: Dalton
  
aif-parameters:
  aifSilWeight: 4
  aifIsoWeight: 2
  aifTopx: 50
  aifCorrelation: 0.8
  aifCorrelationFirstPass: 0.8
  aifMinMass: 0
  aifMsmsTol: 10
  aifSecondPass: false
  aifIterative: false
  aifThresholdFdr: 0.01
  
top-level-parameters:
  slicePeaks: true
  ncores: 1
  ionCountIntensities: false
  maxFeatureDetectionCores: 15
  verboseColumnHeaders: false
  minTime: NaN
  maxTime: NaN
  calcPeakProperties: true
  useOriginalPrecursorMz: false
  multiModificationSearch: false
  advancedRatios: false
  rtShift: false
  fastLfq: true
  randomize: false
  specialAas: KR
  includeContamiants: true
  equalIl: false
  topxWindow: 100
  maxPeptideMass: 5000
  reporterPif: 0.75
  reporterFraction: 0
  reporterBasePeakRatio: 0
  scoreThreshold: 0
  filterAacounts: true
  secondPeptide: true
  matchBetweenRuns: true
  matchBetweenRunsFdr: false
  reQuantify: false
  dependentPeptides: false
  dependentPeptideFdr: 0.01
  dependentPeptideMassBin: 0.0055
  labelFree: false
  lfqMinEdgesPerNode: 3
  lfqAvEdgesPerNode: 6
  hybridQuantification: false
  msmsConnection: false
  ibaq: false
  msmsRecalibration: false
  ibaqLogFit: true
  razorProteinFdr: true
  calcSequenceTags: false
  deNovoVarMods: true
  massDifferenceSearch: false
  minPepLen: 6
  peptideFdr: 0.01
  peptidePep: 1
  proteinFdr: 0.01
  siteFdr: 0.01
  minPeptideLengthForUnspecificSearch: 8
  maxPeptideLengthForUnspecificSearch: 25
  useNormRatiosForOccupancy: true
  minPeptides: 2
  minRazorPeptides: 1
  minUniquePeptides: 0
  useCounterparts: false
  minRatioCount: 2
  lfqMinRatioCount: 2
  restrictProteinQuantification: true
  matchingTimeWindow: 2
  numberOfCandidatesMultiplexedMsms: 50
  numberOfCandidatesMsms: 15
  separateAasForSiteFdr: true
  keepLowScoresMode: 0
  msmsCentroidMode: 1
  quantMode: 1
  siteQuantMode: 0
  tempFolder: false


top-level-strings:
  fixedModifications: Carbamidomethyl (C)
''',
                    default_doubleSILAC='''
fasta-files:
  - uniprot_coli_K12-MG1655_complete-canonical_20110909LP.fasta
                    
restrict-mods:
  - Oxidation (M)
  - Acetyl (Protein N-term)

default-group:
  top-level-parameters:
    maxCharge: 7
    lcmsRunType: 0
    msInstrument: 0
    groupIndex: 1
    maxLabeledAa: 3
    maxNmods: 5
    maxMissedCleavages: 2
    multiplicity: 2
    protease: Trypsin/P
    proteaseFirstSearch: Trypsin/P
    useProteaseFirstSearch: false
    useVariableModificationsFirstSearch: false
    hasAdditionalVariableModifications: false
    doMassFiltering: true
    firstSearchTol: 20
    mainSearchTol: 6
                    
  variableModifications:
    - Oxidation (M)
    - Acetyl (Protein N-term)
                    
  variableModificationsFirstSearch:
    - Oxidation (M)
    - Acetyl (Protein N-term) 
                    
  isobaricLabels:
    - iTRAQ4plex-Nter114
    - iTRAQ4plex-Nter115
    - iTRAQ4plex-Nter116
    - iTRAQ4plex-Nter117
    - iTRAQ4plex-Lys114
    - iTRAQ4plex-Lys115
    - iTRAQ4plex-Lys116
    - iTRAQ4plex-Lys117
  labels:
    - {0}
    - {1}
  
msms-parameters:
  default:
    InPpm: true
    Deisotope: true
    Topx: 10
    HigherCharges: true
    IncludeWater: true
    IncludeAmmonia: true
    DependentLosses: true
  fragment-spectrum-settings:
    FTMS:
      Tolerance:
        Value: 20
        Unit: Ppm
    ITMS:
      InPpm: false
      Deisotope: false
      Topx: 6
      Tolerance:
        Value: 0.5
        Unit: Dalton
    TOF:
      InPpm: false
      Tolerance:
        Value: 0.1
        Unit: Dalton
    Unknown:
      InPpm: false
      Deisotope: false
      Topx: 6
      Tolerance:
        Value: 0.5
        Unit: Dalton
  
aif-parameters:
  aifSilWeight: 4
  aifIsoWeight: 2
  aifTopx: 50
  aifCorrelation: 0.8
  aifCorrelationFirstPass: 0.8
  aifMinMass: 0
  aifMsmsTol: 10
  aifSecondPass: false
  aifIterative: false
  aifThresholdFdr: 0.01
  
top-level-parameters:
  slicePeaks: true
  ncores: 1
  ionCountIntensities: false
  maxFeatureDetectionCores: 15
  verboseColumnHeaders: false
  minTime: NaN
  maxTime: NaN
  calcPeakProperties: true
  useOriginalPrecursorMz: false
  multiModificationSearch: false
  advancedRatios: false
  rtShift: false
  fastLfq: true
  randomize: false
  specialAas: KR
  includeContamiants: true
  equalIl: false
  topxWindow: 100
  maxPeptideMass: 5000
  reporterPif: 0.75
  reporterFraction: 0
  reporterBasePeakRatio: 0
  scoreThreshold: 0
  filterAacounts: true
  secondPeptide: true
  matchBetweenRuns: true
  matchBetweenRunsFdr: false
  reQuantify: false
  dependentPeptides: false
  dependentPeptideFdr: 0.01
  dependentPeptideMassBin: 0.0055
  labelFree: false
  lfqMinEdgesPerNode: 3
  lfqAvEdgesPerNode: 6
  hybridQuantification: false
  msmsConnection: false
  ibaq: false
  msmsRecalibration: false
  ibaqLogFit: true
  razorProteinFdr: true
  calcSequenceTags: false
  deNovoVarMods: true
  massDifferenceSearch: false
  minPepLen: 6
  peptideFdr: 0.01
  peptidePep: 1
  proteinFdr: 0.01
  siteFdr: 0.01
  minPeptideLengthForUnspecificSearch: 8
  maxPeptideLengthForUnspecificSearch: 25
  useNormRatiosForOccupancy: true
  minPeptides: 2
  minRazorPeptides: 1
  minUniquePeptides: 0
  useCounterparts: false
  minRatioCount: 2
  lfqMinRatioCount: 2
  restrictProteinQuantification: true
  matchingTimeWindow: 2
  numberOfCandidatesMultiplexedMsms: 50
  numberOfCandidatesMsms: 15
  separateAasForSiteFdr: true
  keepLowScoresMode: 0
  msmsCentroidMode: 1
  quantMode: 1
  siteQuantMode: 0
  tempFolder: false
  

top-level-strings:
  fixedModifications: Carbamidomethyl (C)
''',
                    default_labelfree='''
fasta-files:
  - uniprot_coli_K12-MG1655_complete-canonical_20110909LP.fasta
                    
restrict-mods:
  - Oxidation (M)
  - Acetyl (Protein N-term)

default-group:
  top-level-parameters:
    maxCharge: 7
    lcmsRunType: 0
    msInstrument: 0
    groupIndex: 1
    maxLabeledAa: 3
    maxNmods: 5
    maxMissedCleavages: 2
    multiplicity: 1
    protease: Trypsin/P
    proteaseFirstSearch: Trypsin/P
    useProteaseFirstSearch: false
    useVariableModificationsFirstSearch: false
    hasAdditionalVariableModifications: false
    doMassFiltering: true
    firstSearchTol: 20
    mainSearchTol: 6
                    
  variableModifications:
    - Oxidation (M)
    - Acetyl (Protein N-term)
                    
  variableModificationsFirstSearch:
    - Oxidation (M)
    - Acetyl (Protein N-term) 
                    
  isobaricLabels:
    - iTRAQ4plex-Nter114
    - iTRAQ4plex-Nter115
    - iTRAQ4plex-Nter116
    - iTRAQ4plex-Nter117
    - iTRAQ4plex-Lys114
    - iTRAQ4plex-Lys115
    - iTRAQ4plex-Lys116
    - iTRAQ4plex-Lys117
  labels:
    - {0}
  
msms-parameters:
  default:
    InPpm: true
    Deisotope: true
    Topx: 10
    HigherCharges: true
    IncludeWater: true
    IncludeAmmonia: true
    DependentLosses: true
  fragment-spectrum-settings:
    FTMS:
      Tolerance:
        Value: 20
        Unit: Ppm
    ITMS:
      InPpm: false
      Deisotope: false
      Topx: 6
      Tolerance:
        Value: 0.5
        Unit: Dalton
    TOF:
      InPpm: false
      Tolerance:
        Value: 0.1
        Unit: Dalton
    Unknown:
      InPpm: false
      Deisotope: false
      Topx: 6
      Tolerance:
        Value: 0.5
        Unit: Dalton
  
aif-parameters:
  aifSilWeight: 4
  aifIsoWeight: 2
  aifTopx: 50
  aifCorrelation: 0.8
  aifCorrelationFirstPass: 0.8
  aifMinMass: 0
  aifMsmsTol: 10
  aifSecondPass: false
  aifIterative: false
  aifThresholdFdr: 0.01
  
top-level-parameters:
  slicePeaks: true
  ncores: 1
  ionCountIntensities: false
  maxFeatureDetectionCores: 15
  verboseColumnHeaders: false
  minTime: NaN
  maxTime: NaN
  calcPeakProperties: true
  useOriginalPrecursorMz: false
  multiModificationSearch: false
  advancedRatios: false
  rtShift: false
  fastLfq: true
  randomize: false
  specialAas: KR
  includeContamiants: true
  equalIl: false
  topxWindow: 100
  maxPeptideMass: 5000
  reporterPif: 0.75
  reporterFraction: 0
  reporterBasePeakRatio: 0
  scoreThreshold: 0
  filterAacounts: true
  secondPeptide: true
  matchBetweenRuns: true
  matchBetweenRunsFdr: false
  reQuantify: false
  dependentPeptides: false
  dependentPeptideFdr: 0.01
  dependentPeptideMassBin: 0.0055
  labelFree: false
  lfqMinEdgesPerNode: 3
  lfqAvEdgesPerNode: 6
  hybridQuantification: false
  msmsConnection: false
  ibaq: false
  msmsRecalibration: false
  ibaqLogFit: true
  razorProteinFdr: true
  calcSequenceTags: false
  deNovoVarMods: true
  massDifferenceSearch: false
  minPepLen: 6
  peptideFdr: 0.01
  peptidePep: 1
  proteinFdr: 0.01
  siteFdr: 0.01
  minPeptideLengthForUnspecificSearch: 8
  maxPeptideLengthForUnspecificSearch: 25
  useNormRatiosForOccupancy: true
  minPeptides: 2
  minRazorPeptides: 1
  minUniquePeptides: 0
  useCounterparts: false
  minRatioCount: 2
  lfqMinRatioCount: 2
  restrictProteinQuantification: true
  matchingTimeWindow: 2
  numberOfCandidatesMultiplexedMsms: 50
  numberOfCandidatesMsms: 15
  separateAasForSiteFdr: true
  keepLowScoresMode: 0
  msmsCentroidMode: 1
  quantMode: 1
  siteQuantMode: 0
  tempFolder: false
  

top-level-strings:
  fixedModifications: Carbamidomethyl (C)
''')
