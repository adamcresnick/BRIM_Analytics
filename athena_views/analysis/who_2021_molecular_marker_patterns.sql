-- ============================================================================
-- WHO 2021 MOLECULAR MARKER PATTERN MATCHING REFERENCE
-- ============================================================================
-- Purpose: Comprehensive pattern matching based on WHO 2021 CNS Tumor
--          Classification for extracting molecular markers from narrative text
--
-- Source: Louis DN et al. The 2021 WHO Classification of Tumors of the
--         Central Nervous System: a summary. Neuro-Oncology 23(8):1231–1251, 2021
--
-- Usage: Reference patterns when implementing molecular marker extraction
--        in v_pathology_diagnostics or other pathology views
--
-- Design: EXTRACTION ONLY - These patterns are used to extract molecular
--         information from narrative text, NOT to filter which reports to include
-- ============================================================================

-- ============================================================================
-- SECTION 1: IDH MUTATION (Adult-type diffuse gliomas)
-- ============================================================================
-- Clinical Significance: Defines glioma subtype; better prognosis than IDH-wildtype
-- WHO 2021 Reference: Table 2, Pages 1236-1237

-- POSITIVE PATTERNS (IDH-mutant = TRUE):
--   'IDH mutant'
--   'IDH-mutant'
--   'IDH1 mutation'
--   'IDH2 mutation'
--   'IDH1 R132H' (most common IDH1 mutation)
--   'IDH1 R132C/G/L/S' (less common IDH1 mutations)
--   'IDH2 R172K/M/W' (IDH2 mutations)
--   'isocitrate dehydrogenase mutant'
--   'isocitrate dehydrogenase mutation'
--   'IDH mut'
--   'IDH+'
--   'positive for IDH'
--   'IDH mutation detected'
--   'IDH mutation identified'
--   'IDH alteration'

-- NEGATIVE PATTERNS (IDH-wildtype = FALSE):
--   'IDH wildtype'
--   'IDH-wildtype'
--   'IDH wild type'
--   'IDH-wild type'
--   'IDH wt'
--   'IDH-wt'
--   'IDH negative'
--   'IDH-'
--   'no IDH mutation'
--   'IDH mutation not detected'
--   'IDH mutation absent'
--   'isocitrate dehydrogenase wildtype'
--   'isocitrate dehydrogenase wild type'

-- ============================================================================
-- SECTION 2: MGMT PROMOTER METHYLATION (Glioblastoma)
-- ============================================================================
-- Clinical Significance: Predicts temozolomide response in GBM
-- WHO 2021 Reference: Table 2, Page 1236

-- POSITIVE PATTERNS (MGMT-methylated = TRUE):
--   'MGMT methylated'
--   'MGMT promoter methylated'
--   'MGMT promoter methylation'
--   'MGMT methylation positive'
--   'MGMT positive'
--   'MGMT+' (in methylation context)
--   'O6-methylguanine-DNA methyltransferase promoter methylation'
--   'MGMT met'
--   'methylated MGMT'
--   'methylated MGMT promoter'

-- NEGATIVE PATTERNS (MGMT-unmethylated = FALSE):
--   'MGMT unmethylated'
--   'MGMT promoter unmethylated'
--   'MGMT methylation negative'
--   'MGMT negative'
--   'MGMT-'
--   'MGMT unmet'
--   'unmethylated MGMT'
--   'no MGMT methylation'
--   'MGMT not methylated'

-- ============================================================================
-- SECTION 3: 1p/19q CODELETION (Oligodendroglioma)
-- ============================================================================
-- Clinical Significance: Defines oligodendroglioma; chemo-sensitive
-- WHO 2021 Reference: Table 2, Page 1236

-- POSITIVE PATTERNS (1p/19q codeleted = TRUE):
--   '1p/19q codeleted'
--   '1p/19q codeletion'
--   '1p 19q codeleted'
--   '1p 19q codeletion'
--   '1p19q codeleted'
--   '1p19q codeletion'
--   'loss of 1p and 19q'
--   '1p and 19q deletion'
--   'chromosome 1p 19q codeletion'
--   '1p/19q codel'
--   '1p/19q LOH' (loss of heterozygosity)
--   '1p/19q loss'

-- NEGATIVE PATTERNS (1p/19q intact = FALSE):
--   '1p/19q intact'
--   '1p/19q not codeleted'
--   '1p 19q intact'
--   'no 1p/19q codeletion'
--   '1p/19q negative'
--   '1p and 19q intact'
--   'no loss of 1p/19q'
--   'retained 1p/19q'

-- ============================================================================
-- SECTION 4: H3 K27 ALTERATION (Diffuse midline glioma)
-- ============================================================================
-- Clinical Significance: Defines diffuse midline glioma; CNS WHO grade 4
-- WHO 2021 Reference: Table 2, Page 1236; "H3 K27-altered" replaces "H3 K27M-mutant"

-- POSITIVE PATTERNS (H3 K27-altered = TRUE):
--   'H3 K27M'
--   'H3 K27M mutation'
--   'H3 K27M mutant'
--   'H3 K27M-mutant'
--   'H3 K27M altered'
--   'H3 K27M-altered'
--   'H3F3A K27M'
--   'HIST1H3B K27M'
--   'H3.3 K27M'
--   'H3.1 K27M'
--   'histone H3 K27M'
--   'H3 K27 mutation'
--   'H3 K27 alteration'
--   'EZHIP overexpression' (alternative mechanism, page 1246)
--   'EZHIP positive'

-- NEGATIVE PATTERNS (H3 K27 wildtype = FALSE):
--   'H3 K27 wildtype'
--   'H3 K27 wild type'
--   'H3 K27 wt'
--   'no H3 K27M mutation'
--   'H3 K27M negative'
--   'EZHIP negative'

-- ============================================================================
-- SECTION 5: H3 G34 MUTATION (Diffuse hemispheric glioma)
-- ============================================================================
-- Clinical Significance: Defines diffuse hemispheric glioma; CNS WHO grade 4
-- WHO 2021 Reference: Table 2, Page 1236

-- POSITIVE PATTERNS (H3 G34-mutant = TRUE):
--   'H3 G34R'
--   'H3 G34V'
--   'H3 G34 mutation'
--   'H3 G34 mutant'
--   'H3F3A G34R'
--   'H3F3A G34V'
--   'H3.3 G34R'
--   'H3.3 G34V'
--   'histone H3 G34 mutation'
--   'H3 G34 alteration'

-- NEGATIVE PATTERNS (H3 G34 wildtype = FALSE):
--   'H3 G34 wildtype'
--   'H3 G34 wild type'
--   'H3 G34 wt'
--   'no H3 G34 mutation'
--   'H3 G34 negative'

-- ============================================================================
-- SECTION 6: BRAF ALTERATIONS (Multiple tumor types)
-- ============================================================================
-- Clinical Significance: Common in pilocytic astrocytoma; targetable with MEK inhibitors
-- WHO 2021 Reference: Table 2, Page 1236

-- POSITIVE PATTERNS:
--   'BRAF V600E'
--   'BRAF V600E mutation'
--   'BRAF V600E mutant'
--   'BRAF mutation'
--   'BRAF mutant'
--   'BRAF altered'
--   'BRAF fusion'
--   'KIAA1549-BRAF fusion'
--   'BRAF-KIAA1549 fusion'
--   'BRAF duplication'
--   'BRAF rearrangement'
--   'BRAF activated'

-- NEGATIVE PATTERNS:
--   'BRAF wildtype'
--   'BRAF wild type'
--   'BRAF wt'
--   'no BRAF mutation'
--   'BRAF negative'

-- ============================================================================
-- SECTION 7: TP53 MUTATION (Multiple tumor types)
-- ============================================================================
-- Clinical Significance: Li-Fraumeni syndrome; high-grade gliomas; medulloblastoma subtyping
-- WHO 2021 Reference: Table 2, Pages 1236-1237

-- POSITIVE PATTERNS:
--   'TP53 mutation'
--   'TP53 mutant'
--   'TP53 altered'
--   'p53 mutation'
--   'p53 mutant'
--   'p53 altered'
--   'TP53 gene mutation'
--   'tumor protein 53 mutation'
--   'p53 overexpression' (surrogate marker)

-- NEGATIVE PATTERNS:
--   'TP53 wildtype'
--   'TP53 wild type'
--   'TP53 wt'
--   'TP53-wildtype'
--   'p53 wildtype'
--   'p53 wild type'
--   'no TP53 mutation'

-- ============================================================================
-- SECTION 8: ATRX LOSS (IDH-mutant astrocytoma)
-- ============================================================================
-- Clinical Significance: Alternative telomere lengthening pathway
-- WHO 2021 Reference: Table 2, Page 1236

-- POSITIVE PATTERNS (ATRX loss = TRUE):
--   'ATRX loss'
--   'ATRX lost'
--   'loss of ATRX'
--   'ATRX negative'
--   'ATRX mutation'
--   'ATRX altered'
--   'absent ATRX'
--   'ATRX deletion'

-- NEGATIVE PATTERNS (ATRX retained = FALSE):
--   'ATRX retained'
--   'ATRX positive'
--   'ATRX intact'
--   'ATRX present'
--   'ATRX expressed'

-- ============================================================================
-- SECTION 9: TERT PROMOTER MUTATION (Glioblastoma, Oligodendroglioma)
-- ============================================================================
-- Clinical Significance: Prognostic in GBM and oligodendroglioma
-- WHO 2021 Reference: Table 2, Pages 1236-1237

-- POSITIVE PATTERNS:
--   'TERT promoter mutation'
--   'TERT mutation'
--   'TERT promoter mutant'
--   'telomerase reverse transcriptase promoter mutation'
--   'TERT C228T'
--   'TERT C250T'
--   'TERT prom mut'

-- NEGATIVE PATTERNS:
--   'TERT wildtype'
--   'TERT wild type'
--   'no TERT mutation'
--   'TERT promoter wildtype'

-- ============================================================================
-- SECTION 10: CDKN2A/B HOMOZYGOUS DELETION (Astrocytoma, Meningioma)
-- ============================================================================
-- Clinical Significance: Indicates CNS WHO grade 4 for IDH-mutant astrocytoma; grade 3 for meningioma
-- WHO 2021 Reference: Table 2, Page 1236; Page 1244

-- POSITIVE PATTERNS:
--   'CDKN2A/B homozygous deletion'
--   'CDKN2A/B deletion'
--   'CDKN2A homozygous deletion'
--   'CDKN2B homozygous deletion'
--   'CDKN2A loss'
--   'CDKN2B loss'
--   'CDKN2A/B loss'
--   'homozygous CDKN2A deletion'
--   'homozygous CDKN2B deletion'

-- NEGATIVE PATTERNS:
--   'CDKN2A/B intact'
--   'CDKN2A/B retained'
--   'no CDKN2A/B deletion'
--   'CDKN2A/B present'

-- ============================================================================
-- SECTION 11: EGFR ALTERATIONS (Glioblastoma)
-- ============================================================================
-- Clinical Significance: Common in IDH-wildtype glioblastoma
-- WHO 2021 Reference: Table 2, Page 1236

-- POSITIVE PATTERNS:
--   'EGFR amplification'
--   'EGFR amplified'
--   'EGFR gene amplification'
--   'EGFR mutation'
--   'EGFRvIII'
--   'EGFR variant III'
--   'EGFR overexpression'
--   'EGFR altered'

-- NEGATIVE PATTERNS:
--   'EGFR not amplified'
--   'no EGFR amplification'
--   'EGFR negative'
--   'EGFR wildtype'

-- ============================================================================
-- SECTION 12: CHROMOSOME 7 GAIN / CHROMOSOME 10 LOSS (+7/-10)
-- ============================================================================
-- Clinical Significance: Indicates glioblastoma even without histologic features
-- WHO 2021 Reference: Page 1239, 1244-1245

-- POSITIVE PATTERNS:
--   '+7/-10'
--   '+7 -10'
--   'gain of chromosome 7 and loss of chromosome 10'
--   'chromosome 7 gain and chromosome 10 loss'
--   'trisomy 7 and monosomy 10'
--   '+7/−10' (with different dash)

-- ============================================================================
-- SECTION 13: MEDULLOBLASTOMA MOLECULAR GROUPS
-- ============================================================================
-- Clinical Significance: Defines medulloblastoma subtypes with different prognoses
-- WHO 2021 Reference: Table 1, Page 1233-1234; Table 2, Page 1236; Pages 1247-1248

-- WNT-ACTIVATED PATTERNS:
--   'WNT-activated'
--   'WNT activated'
--   'WNT pathway activated'
--   'CTNNB1 mutation'
--   'beta-catenin mutation'
--   'APC mutation'
--   'WNT medulloblastoma'

-- SHH-ACTIVATED PATTERNS:
--   'SHH-activated'
--   'SHH activated'
--   'sonic hedgehog activated'
--   'PTCH1 mutation'
--   'SMO mutation'
--   'SUFU mutation'
--   'SHH medulloblastoma'

-- GROUP 3/4 PATTERNS:
--   'non-WNT/non-SHH'
--   'Group 3'
--   'Group 4'
--   'MYC amplification' (Group 3)
--   'MYCN amplification' (Group 3/4)

-- ============================================================================
-- SECTION 14: SMARCB1/SMARCA4 LOSS (Atypical teratoid/rhabdoid tumor)
-- ============================================================================
-- Clinical Significance: Defines AT/RT
-- WHO 2021 Reference: Table 2, Page 1236

-- POSITIVE PATTERNS (SMARCB1/SMARCA4 altered):
--   'SMARCB1 mutation'
--   'SMARCB1 loss'
--   'SMARCA4 mutation'
--   'SMARCA4 loss'
--   'INI1 loss' (protein name for SMARCB1)
--   'BRG1 loss' (protein name for SMARCA4)
--   'loss of INI1'
--   'loss of BRG1'
--   'INI1 negative'
--   'BRG1 negative'

-- ============================================================================
-- SECTION 15: NF2 MUTATION (Meningioma, Spinal ependymoma)
-- ============================================================================
-- Clinical Significance: Common in meningiomas and spinal ependymomas
-- WHO 2021 Reference: Table 2, Page 1236

-- POSITIVE PATTERNS:
--   'NF2 mutation'
--   'NF2 loss'
--   'NF2 alteration'
--   'neurofibromin 2 mutation'
--   'merlin mutation'

-- ============================================================================
-- SECTION 16: EPENDYMOMA MOLECULAR SUBTYPES
-- ============================================================================
-- Clinical Significance: Defines ependymoma subtypes by location
-- WHO 2021 Reference: Table 1, Page 1233; Table 2, Page 1236; Page 1246-1247

-- SUPRATENTORIAL PATTERNS:
--   'ZFTA fusion'
--   'ZFTA-RELA fusion'
--   'C11orf95-RELA fusion' (old nomenclature)
--   'YAP1 fusion'
--   'RELA fusion'

-- POSTERIOR FOSSA PATTERNS:
--   'PFA' or 'group PFA'
--   'PFB' or 'group PFB'
--   'H3 K27me3 loss'
--   'EZHIP overexpression'

-- SPINAL PATTERNS:
--   'MYCN amplification'
--   'MYCN amplified'

-- ============================================================================
-- SECTION 17: WHO GRADE PATTERNS
-- ============================================================================
-- Clinical Significance: WHO grade based on 2021 classification (Arabic numerals)
-- WHO 2021 Reference: Pages 1237-1238; Table 3, Page 1238

-- GRADE PATTERNS (2021 uses Arabic numerals):
--   'CNS WHO grade 1'
--   'CNS WHO grade 2'
--   'CNS WHO grade 3'
--   'CNS WHO grade 4'
--   'WHO grade 1'
--   'WHO grade 2'
--   'WHO grade 3'
--   'WHO grade 4'
--   'Grade 1'
--   'Grade 2'
--   'Grade 3'
--   'Grade 4'

-- LEGACY PATTERNS (pre-2021, Roman numerals):
--   'WHO grade I'
--   'WHO grade II'
--   'WHO grade III'
--   'WHO grade IV'
--   'Grade I'
--   'Grade II'
--   'Grade III'
--   'Grade IV'

-- ============================================================================
-- SECTION 18: HISTOLOGIC TYPE PATTERNS
-- ============================================================================
-- WHO 2021 Reference: Table 1, Pages 1233-1235

-- ADULT-TYPE DIFFUSE GLIOMAS:
--   'astrocytoma, IDH-mutant'
--   'oligodendroglioma, IDH-mutant and 1p/19q-codeleted'
--   'glioblastoma, IDH-wildtype'
--   'glioblastoma'
--   'GBM'
--   'astrocytoma'
--   'oligodendroglioma'
--   'anaplastic astrocytoma' (pre-2021)
--   'anaplastic oligodendroglioma' (pre-2021)

-- PEDIATRIC-TYPE GLIOMAS:
--   'diffuse midline glioma'
--   'DIPG' (diffuse intrinsic pontine glioma)
--   'diffuse hemispheric glioma'
--   'pilocytic astrocytoma'
--   'pleomorphic xanthoastrocytoma'
--   'PXA'

-- EPENDYMOMAS:
--   'ependymoma'
--   'myxopapillary ependymoma'
--   'subependymoma'
--   'anaplastic ependymoma' (pre-2021)

-- EMBRYONAL TUMORS:
--   'medulloblastoma'
--   'atypical teratoid/rhabdoid tumor'
--   'AT/RT'
--   'ATRT'
--   'embryonal tumor'
--   'PNET' (primitive neuroectodermal tumor, outdated)

-- MENINGIOMAS:
--   'meningioma'
--   'atypical meningioma'
--   'anaplastic meningioma'
--   'malignant meningioma'
--   'meningothelial meningioma'
--   'fibrous meningioma'
--   'transitional meningioma'
--   'psammomatous meningioma'
--   'clear cell meningioma'
--   'chordoid meningioma'
--   'papillary meningioma'
--   'rhabdoid meningioma'

-- ============================================================================
-- END OF WHO 2021 MOLECULAR MARKER PATTERNS
-- ============================================================================
