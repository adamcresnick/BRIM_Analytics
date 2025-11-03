

# **A Structured Knowledge Base of the WHO Classification of CNS Tumors (5th Edition) for Computational Diagnosis Mapping**

## **Preamble: How to Use This Document**

This document is a comprehensive, structured knowledge base designed to function as a primary technical reference for a computational (LLM) agent. Its purpose is to facilitate the mapping of patient data from unstructured Electronic Health Records (EHRs) to the standardized nomenclature of the 2021 World Health Organization (WHO) Classification of Tumors of the Central Nervous System, 5th Edition (WHO CNS5).

The entire report is synthesized from the summary and tables of the definitive publication: Louis et al., "The 2021 WHO Classification of Tumors of the Central Nervous System: a summary" (*Neuro-Oncology*, 2021).1

The knowledge base is organized by the major taxonomic groupings of the WHO CNS5. For every tumor type and subtype, a consistent, structured schema is used. This schema is designed for machine parsing and provides a "ground truth" for the agent to query against. The successful classification of legacy cases, particularly from a natural history study, depends on the agent's ability to cross-reference histological descriptions, demographic data, and (where available) molecular findings from older reports against the defining criteria presented in this document.

## **Section 1: Key Diagnostic Principles for the LLM Agent**

To successfully utilize this knowledge base, the agent's workflow must adopt the core classification logic introduced in the WHO CNS5. The following principles, derived from the "General Changes" in the source document, are foundational.1

### **1.1 The Primacy of Age and Location in Diagnostic Triage**

The WHO CNS5 formalizes a concept critical for pediatric neurooncology: the diagnostic pathway is fundamentally dependent on patient age and tumor location. The classification now formally separates diffuse gliomas into "Adult-type" and "Pediatric-type" categories.1

This division is not merely descriptive; it is the primary sorting key. An agent's workflow must, therefore, first extract Age and Location before attempting to classify a glioma.

* **Example 1 (Age):** A diagnosis of "Glioblastoma" in a 5-year-old is now exceptionally rare and likely represents a "Diffuse pediatric-type high-grade glioma, H3-wildtype and IDH-wildtype" or another pediatric entity. The term "Glioblastoma, IDH-wildtype" is reserved almost exclusively for adults.1  
* **Example 2 (Location):** The classification of ependymomas is now stratified *first* by location (Supratentorial, Posterior Fossa, Spinal) and *then* by molecular alteration.1 Similarly, a diffuse high-grade glioma in a child located in the brainstem ("midline") initiates a diagnostic pathway for Diffuse midline glioma, H3 K27-altered, whereas the same tumor in the frontal lobe ("hemispheric") initiates a pathway for Diffuse hemispheric glioma, H3 G34-mutant.1

The Key Demographics & Location field in this report must be used by the agent as a primary sorting variable, not as secondary metadata.

### **1.2 Mapping from Previous Designations (Nomenclature Translation)**

A major challenge for a natural history study is the obsolescence of prior nomenclature. The WHO CNS5 has eliminated many familiar terms to improve diagnostic precision.1 An agent reading an EHR from 2010 will frequently encounter these obsolete terms.

The Previous Designation(s) field in this document is the agent's translation dictionary.

* **Example 1 (Gliomas):** The terms "Anaplastic Astrocytoma, IDH-mutant" and "Glioblastoma, IDH-mutant" are no longer used. Both are now classified as Astrocytoma, IDH-mutant and assigned a CNS WHO grade of 3 or 4, respectively.1 The agent must map the old name to the new name and then assign the correct grade.  
* **Example 2 (Mesenchymal):** The term "Hemangiopericytoma" has been retired. All such diagnoses must be mapped by the agent to Solitary fibrous tumor.1  
* **Example 3 (Pineal):** The name for Diffuse midline glioma, H3 K27M-mutant was changed to Diffuse midline glioma, H3 K27-altered. This is not just a semantic change; it *expands* the diagnosis to include tumors with EZHIP overexpression that mimic the H3K27 mutation, a critical distinction for a natural history study.1

### **1.3 The Grading Within Type Principle and Molecular Modifiers**

Grading has been fundamentally altered. Previously, grade was tied to the *entity* (e.g., "Anaplastic Astrocytoma" *was* Grade III). Now, grade is applied *within* a tumor type (e.g., Meningioma is a single type, with grades 1, 2, and 3 applied based on features).1

Most critically, molecular parameters can *override* histological grade. The agent's grading workflow must be:

1. Establish histological grade from the pathology report (if present).  
2. Search the genomic report for specific Molecular Grading Markers.  
3. If a marker is found, apply the WHO CNS5-mandated grade, even if it *contradicts* the histological-only impression.

**Key Molecular Grading Triggers for the Agent:**

* **Trigger 1:** If Diagnosis \= Astrocytoma, IDH-mutant AND Molecular Finding \= CDKN2A/B homozygous deletion, THEN CNS WHO Grade \= 4\. This is true *regardless* of histological features (i.e., a tumor that looks like Grade 2 is elevated to Grade 4).1  
* **Trigger 2:** If Diagnosis \= IDH-wildtype diffuse astrocytoma (histologically Grade 2 or 3\) AND Molecular Finding \= (TERT promoter mutation OR EGFR gene amplification OR \+7/-10 copy number changes), THEN Diagnosis \= Glioblastoma, IDH-wildtype AND CNS WHO Grade \= 4\. These molecular features are sufficient for a Grade 4 diagnosis even without the classic histology of microvascular proliferation or necrosis.1  
* **Trigger 3:** If Diagnosis \= Meningioma (any histological subtype) AND Molecular Finding \= (TERT promoter mutation OR CDKN2A/B homozygous deletion), THEN CNS WHO Grade \= 3\.1

### **1.4 Interpreting "NOS" (Not Otherwise Specified) and "NEC" (Not Elsewhere Classified)**

The suffixes "NOS" and "NEC" are now standardized diagnostic tools for handling data ambiguity and are essential for a retrospective study.1 The agent must be programmed to apply them correctly.

* **NOS (Not Otherwise Specified):** The agent must apply this suffix when a specific WHO diagnosis *requires* molecular information (e.g., Oligodendroglioma requires IDH mutation and 1p/19q codeletion) but the EHR provides *no* information on that testing (e.g., a pre-2010 report).  
  * **Workflow:** An EHR diagnosis of "Oligodendroglioma" (histology only) with no molecular data would be mapped by the agent to: Oligodendroglioma, IDH-mutant, and 1p/19q-codeleted, NOS. This flags the diagnosis as incomplete but histologically suggestive.  
* **NEC (Not Elsewhere Classified):** The agent must apply this suffix when the necessary diagnostic testing *was performed*, but the results are *contradictory*, *nondiagnostic*, or *do not fit* any defined WHO category.  
  * **Workflow:** An EHR shows a tumor with "astrocytic" histology, an IDH1 mutation, but *also* a 1p/19q codeletion. This combination is biologically contradictory and does not fit Astrocytoma (which is 1p/19q intact) or Oligodendroglioma (which is 1p/19q codeleted). The agent should not choose one; it should flag this as Diffuse Glioma, NEC (Not Elsewhere Classified) and alert for manual review.

## **Section 2: Structured Knowledge Base: Tumor Classification**

This section provides the exhaustive, structured data for all CNS tumor types and subtypes listed in the WHO CNS5.1

### **2.1 Gliomas, Glioneuronal Tumors, and Neuronal Tumors**

This major grouping is now divided into six families: (1) Adult-type diffuse gliomas, (2) Pediatric-type diffuse low-grade gliomas, (3) Pediatric-type diffuse high-grade gliomas, (4) Circumscribed astrocytic gliomas, (5) Glioneuronal and neuronal tumors, and (6) Ependymal tumors.1

#### **Adult-type diffuse gliomas**

This family comprises the most common primary brain tumors in adults.1

##### **Astrocytoma, IDH-mutant**

* **Diagnosis (WHO CNS5):** Astrocytoma, IDH-mutant  
* **Taxonomic Group:** Gliomas... / Adult-type diffuse gliomas  
* **Previous Designation(s):** Diffuse astrocytoma, IDH-mutant (WHO 2016, Grade 2); Anaplastic astrocytoma, IDH-mutant (WHO 2016, Grade 3); Glioblastoma, IDH-mutant (WHO 2016, Grade 4).1 This single type now covers all three previous entities.  
* **CNS WHO Grade:** 2, 3, or 4\.1 Grading is based on histology (Grade 2 \= low-grade; Grade 3 \= "anaplastic" features; Grade 4 \= necrosis and/or microvascular proliferation) *OR* molecular criteria.  
* **Key Demographics & Location:** Primarily adults. Typically located in the cerebral hemispheres.1  
* **Histological Features:** A diffusely infiltrating astrocytic glioma.  
* **Essential Molecular Features (Definitional):** Presence of an $IDH1$ or $IDH2$ mutation *AND* absence of $1p/19q$ codeletion.1  
* **Characteristic Molecular Features (Supportive):** Loss of nuclear $ATRX$ expression (or $ATRX$ mutation) and $TP53$ mutation are characteristic.1  
* **Molecular Grading Markers:** Homozygous deletion of $CDKN2A/B$ automatically confers a CNS WHO grade 4, *regardless* of the histological appearance.1  
* **Source Reference(s):** 1

##### **Oligodendroglioma, IDH-mutant, and 1p/19q-codeleted**

* **Diagnosis (WHO CNS5):** Oligodendroglioma, IDH-mutant, and 1p/19q-codeleted  
* **Taxonomic Group:** Gliomas... / Adult-type diffuse gliomas  
* **Previous Designation(s):** Oligodendroglioma (WHO 2016, Grade 2); Anaplastic oligodendroglioma (WHO 2016, Grade 3).1  
* **CNS WHO Grade:** 2 or 3\.1 Grading is based on histological features (e.g., mitotic activity).  
* **Key Demographics & Location:** Primarily adults. Typically located in the cerebral hemispheres.1  
* **Histological Features:** A diffusely infiltrating glioma. Classic "oligodendroglial" features (round nuclei, perinuclear halos or "fried egg" cells, delicate branching capillaries) are common but *not* sufficient for diagnosis.1  
* **Essential Molecular Features (Definitional):** Presence of an $IDH1$ or $IDH2$ mutation *AND* the presence of whole-arm $1p/19q$ codeletion.1  
* **Characteristic Molecular Features (Supportive):** $TERT$ promoter mutation is very common. Mutations in $CIC$, $FUBP1$, and $NOTCH1$ are also characteristic.1  
* **Molecular Grading Markers:** None specified in.1  
* **Source Reference(s):** 1

##### **Glioblastoma, IDH-wildtype**

* **Diagnosis (WHO CNS5):** Glioblastoma, IDH-wildtype  
* **Taxonomic Group:** Gliomas... / Adult-type diffuse gliomas  
* **Previous Designation(s):** Glioblastoma (WHO 2016, Grade 4). This diagnosis *also* now incorporates tumors previously called "Diffuse astrocytoma, IDH-wildtype" or "Anaplastic astrocytoma, IDH-wildtype" *if* they possess specific molecular features.1  
* **CNS WHO Grade:** 4\.1  
* **Key Demographics & Location:** Primarily adults, particularly older adults (\>55 years). Cerebral hemispheres.1 An IDH-wildtype diffuse glioma in a pediatric patient should be evaluated for pediatric-type entities.1  
* **Histological Features:** A diffusely infiltrating, high-grade astrocytic glioma.  
* **Essential Molecular Features (Definitional):** $IDH1$ and $IDH2$ wildtype status is required.1 Diagnosis as Glioblastoma, Grade 4, is established if *EITHER* of the following are met:  
  1. **Histological Criteria:** Necrosis and/or microvascular proliferation are present.  
  2. **Molecular Criteria:** The tumor is a histologically lower-grade (Grade 2 or 3\) diffuse astrocytoma but possesses one or more of the following: $TERT$ promoter mutation, $EGFR$ gene amplification, OR combined gain of entire chromosome 7 and loss of entire chromosome 10 ($+7/-10$).1  
* **Characteristic Molecular Features (Supportive):** Histological variants (now subtypes) include Giant cell glioblastoma and Gliosarcoma.1  
* **Source Reference(s):** 1

#### **Pediatric-type diffuse low-grade gliomas**

This is a new family of tumors that occur primarily in children and are expected to have good prognoses.1

##### **Diffuse astrocytoma, MYB- or MYBL1-altered**

* **Diagnosis (WHO CNS5):** Diffuse astrocytoma, MYB- or MYBL1-altered  
* **Taxonomic Group:** Gliomas... / Pediatric-type diffuse low-grade gliomas  
* **Previous Designation(s):** Newly recognized type.1 May have been previously classified as "Diffuse Astrocytoma, NOS."  
* **CNS WHO Grade:** 1\.1  
* **Key Demographics & Location:** Primarily pediatric.1  
* **Histological Features:** Diffusely infiltrating glioma.1  
* **Essential Molecular Features (Definitional):** Alteration (e.g., fusion or duplication) of the $MYB$ or $MYBL1$ gene.1  
* **Source Reference(s):** 1

##### **Angiocentric glioma**

* **Diagnosis (WHO CNS5):** Angiocentric glioma  
* **Taxonomic Group:** Gliomas... / Pediatric-type diffuse low-grade gliomas  
* **Previous Designation(s):** Angiocentric glioma (WHO 2016).  
* **CNS WHO Grade:** 1 (Implied by inclusion in this group; not listed in Table 3).1  
* **Key Demographics & Location:** Primarily pediatric.1  
* **Histological Features:** Diffusely infiltrating glioma with a characteristic angiocentric (perivascular) growth pattern.1  
* **Essential Molecular Features (Definitional):** $MYB$ gene alteration, most commonly a $MYB-QKI$ fusion.1  
* **Source Reference(s):** 1

##### **Polymorphous low-grade neuroepithelial tumor of the young (PLNTY)**

* **Diagnosis (WHO CNS5):** Polymorphous low-grade neuroepithelial tumor of the young  
* **Taxonomic Group:** Gliomas... / Pediatric-type diffuse low-grade gliomas  
* **Previous Designation(s):** Newly recognized type.1  
* **CNS WHO Grade:** 1\.1  
* **Key Demographics & Location:** Young people (pediatric/young adult), associated with a history of epilepsy.1  
* **Histological Features:** Diffuse growth patterns, frequent presence of oligodendroglioma-like components, calcification, and a polymorphous (variable) appearance. Strong and diffuse CD34 immunoreactivity is typical.1  
* **Essential Molecular Features (Definitional):** An activating genetic abnormality in the $MAPK$ pathway.1  
* **Characteristic Molecular Features (Supportive):** Alterations in $BRAF$ (e.g., V600E mutation) or $FGFR$ family genes (e.g., $FGFR2$ or $FGFR3$ fusions).1  
* **Source Reference(s):** 1

##### **Diffuse low-grade glioma, MAPK pathway-altered**

* **Diagnosis (WHO CNS5):** Diffuse low-grade glioma, MAPK pathway-altered  
* **Taxonomic Group:** Gliomas... / Pediatric-type diffuse low-grade gliomas  
* **Previous Designation(s):** Newly recognized type.1 This is a broad "matrix" diagnosis.  
* **CNS WHO Grade:** Not assigned as a whole.1 Grade depends on the specific integrated diagnosis.  
* **Key Demographics & Location:** Pediatric.1  
* **Histological Features:** Diffuse glioma that can have either an astrocytic or oligodendroglial morphology. Diagnosis requires an integrated, layered report combining histology and molecular data.1  
* **Essential Molecular Features (Definitional):** An alteration in the $MAPK$ pathway.1  
* **Characteristic Molecular Features (Supportive):** Most commonly $FGFR1$ alterations (e.g., tyrosine kinase domain (TKD) duplications, $FGFR1-TACC1$ fusion) or $BRAF$ alterations (e.g., V600E mutation, $KIAA1549-BRAF$ fusion).1  
* **Source Reference(s):** 1

#### **Pediatric-type diffuse high-grade gliomas**

This is a new family of tumors that occur primarily in children and behave aggressively.1

##### **Diffuse midline glioma, H3 K27-altered**

* **Diagnosis (WHO CNS5):** Diffuse midline glioma, H3 K27-altered  
* **Taxonomic Group:** Gliomas... / Pediatric-type diffuse high-grade gliomas  
* **Previous Designation(s):** Diffuse midline glioma, H3 K27M-mutant (WHO 2016).1  
* **CNS WHO Grade:** 4 (Implied by high-grade family, and consistent with 2016).1  
* **Key Demographics & Location:** Primarily pediatric.1 Occurs *exclusively* in midline structures (e.g., thalamus, brainstem, spinal cord).1  
* **Histological Features:** Diffusely infiltrating, high-grade astrocytic glioma.  
* **Essential Molecular Features (Definitional):** The nomenclature changed from "K27M-mutant" to "K27-altered" to recognize *alternative mechanisms* of disrupting H3K27 methylation.1 Diagnosis is established by:  
  1. An $H3 K27$ mutation (e.g., $H3F3A$ p.Lys28Met (K27M), $HIST1H3B$ p.Lys28Met (K27M)).1  
  2. *OR* $EZHIP$ protein overexpression (which mimics the mutation).1  
* **Characteristic Molecular Features (Supportive):** $TP53$ mutations, $ACVR1$ mutations, and $PDGFRA$ or $EGFR$ amplification are common.1  
* **Source Reference(s):** 1

##### **Diffuse hemispheric glioma, H3 G34-mutant**

* **Diagnosis (WHO CNS5):** Diffuse hemispheric glioma, H3 G34-mutant  
* **Taxonomic Group:** Gliomas... / Pediatric-type diffuse high-grade gliomas  
* **Previous Designation(s):** Newly recognized type.1 Previously often classified as "Glioblastoma, IDH-wildtype."  
* **CNS WHO Grade:** 4\.1  
* **Key Demographics & Location:** Primarily pediatric and young adults.1 Occurs in the *cerebral hemispheres*.1  
* **Histological Features:** Malignant, infiltrative glioma, sometimes with high-grade anaplastic or embryonal-appearing features.1  
* **Essential Molecular Features (Definitional):** A missense mutation in an $H3$ gene (e.g., $H3F3A$) resulting in a p.Gly35Arg/Val (G34R/V) substitution.1  
* **Characteristic Molecular Features (Supportive):** $TP53$ and $ATRX$ mutations are characteristic.1  
* **Source Reference(s):** 1

##### **Diffuse pediatric-type high-grade glioma, H3-wildtype and IDH-wildtype**

* **Diagnosis (WHO CNS5):** Diffuse pediatric-type high-grade glioma, H3-wildtype and IDH-wildtype  
* **Taxonomic Group:** Gliomas... / Pediatric-type diffuse high-grade gliomas  
* **Previous Designation(s):** Newly recognized type.1 This is a "catch-all" diagnosis for pediatric high-grade gliomas that do not fit other molecularly-defined categories.  
* **CNS WHO Grade:** 4 (Implied by high-grade).1  
* **Key Demographics & Location:** Pediatric.1  
* **Histological Features:** Diffusely infiltrating, high-grade glioma.  
* **Essential Molecular Features (Definitional):** Wildtype status for all $H3$ and $IDH$ genes is required.1  
* **Characteristic Molecular Features (Supportive):** This is a heterogeneous group defined by what it *lacks*. Tumors in this category often have other driver alterations, such as $PDGFRA$ amplification, $MYCN$ amplification, or $EGFR$ amplification. DNA methylation profiling is often critical for classification.1  
* **Source Reference(s):** 1

##### **Infant-type hemispheric glioma**

* **Diagnosis (WHO CNS5):** Infant-type hemispheric glioma  
* **Taxonomic Group:** Gliomas... / Pediatric-type diffuse high-grade gliomas  
* **Previous Designation(s):** Newly recognized type.1  
* **CNS WHO Grade:** High-grade (Grade 3 or 4).1  
* **Key Demographics & Location:** Newborns and infants.1 Occurs in the cerebral hemispheres.  
* **Histological Features:** High-grade glioma.1  
* **Essential Molecular Features (Definitional):** Characterized by fusion genes involving Receptor Tyrosine Kinases (RTKs), specifically $NTRK$ family ($NTRK1/2/3$), $ALK$, $ROS1$, or $MET$.1  
* **Source Reference(s):** 1

#### **Circumscribed astrocytic gliomas**

This family consists of astrocytic tumors that are "circumscribed" (more solid, less infiltrative) as opposed to the "diffuse" gliomas.1

##### **Pilocytic astrocytoma**

* **Diagnosis (WHO CNS5):** Pilocytic astrocytoma  
* **Taxonomic Group:** Gliomas... / Circumscribed astrocytic gliomas  
* **Previous Designation(s):** Pilocytic astrocytoma (WHO 2016).  
* **CNS WHO Grade:** 1\.  
* **Key Demographics & Location:** Primarily children and young adults. Classic locations include the cerebellum, optic pathway, and brainstem.  
* **Histological Features:** Circumscribed, often cystic with a mural nodule. Classically biphasic, with compact, piloid areas (containing Rosenthal fibers) and loose, microcystic areas (containing eosinophilic granular bodies).  
* **Essential Molecular Features (Definitional):** Alteration in the $MAPK$ pathway.1  
* **Characteristic Molecular Features (Supportive):** The most common alteration is the $KIAA1549-BRAF$ fusion. Other alterations include $BRAF$ V600E mutation or $NF1$ mutation (in Neurofibromatosis type 1 patients).1  
* **Source Reference(s):** 1

##### **High-grade astrocytoma with piloid features**

* **Diagnosis (WHO CNS5):** High-grade astrocytoma with piloid features  
* **Taxonomic Group:** Gliomas... / Circumscribed astrocytic gliomas  
* **Previous Designation(s):** Newly recognized type.1 May have been previously classified as "Anaplastic Pilocytic Astrocytoma."  
* **CNS WHO Grade:** High-grade (Grade 3 or 4).  
* **Key Demographics & Location:** N/A from source.  
* **Histological Features:** Possesses "piloid features" (resembling pilocytic astrocytoma) but also has high-grade features (e.g., high mitotic activity, necrosis).  
* **Characteristic Molecular Features (Supportive):** Often shows a combination of a $MAPK$ pathway alteration (e.g., $BRAF$ or $NF1$) *plus* molecular features of a high-grade glioma, such as $ATRX$ mutation and/or $CDKN2A/B$ homozygous deletion. DNA methylation profiling is often key for diagnosis.1  
* **Source Reference(s):** 1

##### **Pleomorphic xanthoastrocytoma**

* **Diagnosis (WHO CNS5):** Pleomorphic xanthoastrocytoma (PXA)  
* **Taxonomic Group:** Gliomas... / Circumscribed astrocytic gliomas  
* **Previous Designation(s):** Pleomorphic xanthoastrocytoma (WHO 2016); Anaplastic Pleomorphic Xanthoastrocytoma (WHO 2016).  
* **CNS WHO Grade:** 2 or 3\.1  
* **Key Demographics & Location:** Children and young adults. Typically superficial (supratentorial, temporal lobe) and associated with epilepsy.  
* **Histological Features:** Circumscribed. Highly pleomorphic (variable) cells, including lipidized "xanthomatous" cells, bizarre multinucleated giant cells, and eosinophilic granular bodies.  
* **Essential Molecular Features (Definitional):** $BRAF$ V600E mutation is a characteristic and defining feature.1  
* **Molecular Grading Markers:** Presence of $CDKN2A/B$ homozygous deletion is associated with Grade 3 and more aggressive behavior.1  
* **Source Reference(s):** 1

##### **Subependymal giant cell astrocytoma (SEGA)**

* **Diagnosis (WHO CNS5):** Subependymal giant cell astrocytoma  
* **Taxonomic Group:** Gliomas... / Circumscribed astrocytic gliomas  
* **Previous Designation(s):** Subependymal giant cell astrocytoma (WHO 2016).  
* **CNS WHO Grade:** 1\.  
* **Key Demographics & Location:** Children and young adults. *Strongly* associated with Tuberous Sclerosis Complex (TSC) genetic syndrome. Located intraventricularly (subependymal), typically near the foramen of Monro.  
* **Histological Features:** Circumscribed. Composed of large, ganglion-like cells.  
* **Essential Molecular Features (Definitional):** Inactivation of the $TSC1$ or $TSC2$ genes, consistent with the TSC syndrome.1  
* **Source Reference(s):** 1

##### **Chordoid glioma**

* **Diagnosis (WHO CNS5):** Chordoid glioma  
* **Taxonomic Group:** Gliomas... / Circumscribed astrocytic gliomas  
* **Previous Designation(s):** Chordoid glioma of the third ventricle (WHO 2016). The location modifier was removed from the *name*.1  
* **CNS WHO Grade:** 2 (Traditional grade, not listed in Table 3).  
* **Key Demographics & Location:** Adults. Highly characteristic location in the third ventricle, even though this is no longer part of the name.1  
* **Histological Features:** Circumscribed. Features "chordoid" morphology (cells arranged in cords or nests within a prominent myxoid/mucinous stroma).  
* **Essential Molecular Features (Definitional):** A characteristic $PRKCA$ gene mutation.1  
* **Source Reference(s):** 1

##### **Astroblastoma, MN1-altered**

* **Diagnosis (WHO CNS5):** Astroblastoma, MN1-altered  
* **Taxonomic Group:** Gliomas... / Circumscribed astrocytic gliomas  
* **Previous Designation(s):** Astroblastoma (WHO 2016). The genetic modifier $MN1-altered$ has been added to provide diagnostic focus.1  
* **CNS WHO Grade:** N/A from source (historically variable).  
* **Key Demographics & Location:** N/A from source.  
* **Histological Features:** Circumscribed. Classic "astroblastic pseudorosettes" where tumor cells are arranged radially around a central blood vessel.1  
* **Essential Molecular Features (Definitional):** $MN1$ gene alteration (e.g., fusion).1  
* **Source Reference(s):** 1

#### **Glioneuronal and neuronal tumors**

A diverse group of tumors featuring neuronal or mixed glioneuronal differentiation.1

##### **Ganglioglioma**

* **Diagnosis (WHO CNS5):** Ganglioglioma  
* **Taxonomic Group:** Gliomas... / Glioneuronal and neuronal tumors  
* **Previous Designation(s):** Ganglioglioma (WHO 2016).  
* **CNS WHO Grade:** 1\. (The anaplastic variant is Grade 3).  
* **Key Demographics & Location:** Children and young adults. Often in the temporal lobe, a common cause of focal epilepsy.  
* **Histological Features:** Circumscribed. Biphasic tumor composed of a glial component (neoplastic astrocytes) and a neuronal component (large, dysplastic ganglion cells).  
* **Characteristic Molecular Features (Supportive):** $MAPK$ pathway alterations are characteristic, most commonly the $BRAF$ V600E mutation. $BRAF$ fusions can also occur.1  
* **Source Reference(s):** 1

##### **Desmoplastic infantile ganglioglioma/desmoplastic infantile astrocytoma (DIG/DIA)**

* **Diagnosis (WHO CNS5):** Desmoplastic infantile ganglioglioma/desmoplastic infantile astrocytoma  
* **Taxonomic Group:** Gliomas... / Glioneuronal and neuronal tumors  
* **Previous Designation(s):** Same (WHO 2016).  
* **CNS WHO Grade:** 1\.  
* **Key Demographics & Location:** Infants (typically \< 1 year).  
* **Histological Features:** Very large, superficial, cystic tumors. Prominent "desmoplastic" (fibrous) stroma. The DIA component is purely astrocytic, while the DIG component also has neuronal elements.  
* **Source Reference(s):** 1

##### **Dysembryoplastic neuroepithelial tumor (DNET)**

* **Diagnosis (WHO CNS5):** Dysembryoplastic neuroepithelial tumor  
* **Taxonomic Group:** Gliomas... / Glioneuronal and neuronal tumors  
* **Previous Designation(s):** DNET (WHO 2016).  
* **CNS WHO Grade:** 1\.  
* **Key Demographics & Location:** Children and young adults. Strongly associated with intractable, focal epilepsy. Typically cortical.  
* **Histological Features:** Nodular, often multinodular. Characterized by the "specific glioneuronal element," which includes columns of axons lined by small oligodendrocyte-like cells, with "floating" neurons in a myxoid stroma.  
* **Characteristic Molecular Features (Supportive):** $FGFR1$ alterations (e.g., TKD duplications) are common. $BRAF$ V600E mutations also occur.1  
* **Source Reference(s):** 1

##### **Diffuse glioneuronal tumor with oligodendroglioma-like features and nuclear clusters**

* **Diagnosis (WHO CNS5):** Diffuse glioneuronal tumor with oligodendroglioma-like features and nuclear clusters  
* **Taxonomic Group:** Gliomas... / Glioneuronal and neuronal tumors  
* **Previous Designation(s):** Newly recognized provisional type.1  
* **CNS WHO Grade:** N/A from source.  
* **Key Demographics & Location:** N/A from source.  
* **Histological Features:** Diffuse glioneuronal tumor with oligodendroglioma-like cells and "nuclear clusters."  
* **Characteristic Molecular Features (Supportive):** Chromosome 14 alterations. DNA methylation profiling is important for diagnosis.1  
* **Source Reference(s):** 1

##### **Papillary glioneuronal tumor**

* **Diagnosis (WHO CNS5):** Papillary glioneuronal tumor  
* **Taxonomic Group:** Gliomas... / Glioneuronal and neuronal tumors  
* **Previous Designation(s):** Papillary glioneuronal tumor (WHO 2016).  
* **CNS WHO Grade:** 1\.  
* **Key Demographics & Location:** N/A from source.  
* **Histological Features:** Papillary architecture (pseudopapillae with hyalinized vascular cores) and a mix of glial and neuronal cells.  
* **Characteristic Molecular Features (Supportive):** $PRKCA$ fusions are characteristic.1  
* **Source Reference(s):** 1

##### **Rosette-forming glioneuronal tumor**

* **Diagnosis (WHO CNS5):** Rosette-forming glioneuronal tumor  
* **Taxonomic Group:** Gliomas... / Glioneuronal and neuronal tumors  
* **Previous Designation(s):** Rosette-forming glioneuronal tumor (WHO 2016).  
* **CNS WHO Grade:** 1\.  
* **Key Demographics & Location:** Typically in the 4th ventricle or cerebellum.  
* **Histological Features:** Biphasic, with (1) neurocytic rosettes/perivascular pseudorosettes and (2) a pilocytic astrocytoma-like glial component.  
* **Characteristic Molecular Features (Supportive):** Alterations in $FGFR1$ (e.g., mutations, $FGFR1-TACC1$ fusion), $PIK3CA$, or $NF1$ are common.1  
* **Source Reference(s):** 1

##### **Myxoid glioneuronal tumor**

* **Diagnosis (WHO CNS5):** Myxoid glioneuronal tumor  
* **Taxonomic Group:** Gliomas... / Glioneuronal and neuronal tumors  
* **Previous Designation(s):** Newly recognized type.1  
* **CNS WHO Grade:** N/A from source.  
* **Key Demographics & Location:** Typically arises in the septal region, may involve the lateral ventricles.1  
* **Histological Features:** Proliferation of oligodendrocyte-like tumor cells embedded in a prominent *myxoid stroma*. May have admixed "floating neurons," neurocytic rosettes, or perivascular neuropil.1  
* **Essential Molecular Features (Definitional):** A characteristic dinucleotide mutation in $PDGFRA$.1  
* **Source Reference(s):** 1

##### **Diffuse leptomeningeal glioneuronal tumor**

* **Diagnosis (WHO CNS5):** Diffuse leptomeningeal glioneuronal tumor  
* **Taxonomic Group:** Gliomas... / Glioneuronal and neuronal tumors  
* **Previous Designation(s):** Diffuse leptomeningeal glioneuronal tumor (WHO 2016).  
* **CNS WHO Grade:** N/A from source (variable, but often aggressive).  
* **Key Demographics & Location:** Primarily children. Diffuse "sugar-coating" of the leptomeninges (brain and spinal cord surface).  
* **Histological Features:** Diffuse proliferation of oligodendrocyte-like cells and neuronal elements in the leptomeninges.  
* **Characteristic Molecular Features (Supportive):** $KIAA1549-BRAF$ fusion (same as in pilocytic astrocytoma) is common. Loss of chromosome 1p is also characteristic. DNA methylation profiling is useful.1  
* **Source Reference(s):** 1

##### **Gangliocytoma**

* **Diagnosis (WHO CNS5):** Gangliocytoma  
* **Taxonomic Group:** Gliomas... / Glioneuronal and neuronal tumors  
* **Previous Designation(s):** Gangliocytoma (WHO 2016).  
* **CNS WHO Grade:** 1\.  
* **Key Demographics & Location:** N/A from source.  
* **Histological Features:** Composed purely of neoplastic, dysplastic ganglion cells (neuronal component) *without* a neoplastic glial component (distinguishing it from ganglioglioma).  
* **Source Reference(s):** 1

##### **Multinodular and vacuolating neuronal tumor**

* **Diagnosis (WHO CNS5):** Multinodular and vacuolating neuronal tumor  
* **Taxonomic Group:** Gliomas... / Glioneuronal and neuronal tumors  
* **Previous Designation(s):** Newly recognized type.1 (Was discussed in 2016 but not a formal type).  
* **CNS WHO Grade:** 1\.1  
* **Key Demographics & Location:** Often associated with epilepsy.  
* **Histological Features:** Benign. Composed of monomorphous neuronal elements in discrete, coalescent nodules. Features "vacuolar" changes in both the tumor cells and the surrounding neuropil.1  
* **Characteristic Molecular Features (Supportive):** Alteration in the $MAPK$ pathway.1  
* **Source Reference(s):** 1

##### **Dysplastic cerebellar gangliocytoma (Lhermitte-Duclos disease)**

* **Diagnosis (WHO CNS5):** Dysplastic cerebellar gangliocytoma (Lhermitte-Duclos disease)  
* **Taxonomic Group:** Gliomas... / Glioneuronal and neuronal tumors  
* **Previous Designation(s):** Same (WHO 2016).  
* **CNS WHO Grade:** 1 (often considered a hamartoma).  
* **Key Demographics & Location:** Associated with Cowden syndrome (germinoma $PTEN$ mutation). Located in the cerebellum.  
* **Histological Features:** Dysplastic, disorganized expansion of the cerebellar folia by abnormal ganglion cells.  
* **Essential Molecular Features (Definitional):** Germline or somatic $PTEN$ mutation.1  
* **Source Reference(s):** 1

##### **Central neurocytoma**

* **Diagnosis (WHO CNS5):** Central neurocytoma  
* **Taxonomic Group:** Gliomas... / Glioneuronal and neuronal tumors  
* **Previous Designation(s):** Central neurocytoma (WHO 2016).  
* **CNS WHO Grade:** 2\.  
* **Key Demographics & Location:** Young adults. Characteristic "central" location, i.e., intraventricular (lateral or third ventricle), often attached to the septum pellucidum.  
* **Histological Features:** Composed of uniform, round neuronal cells with neurocytic rosettes or perivascular pseudorosettes.  
* **Source Reference(s):** 1

##### **Extraventricular neurocytoma**

* **Diagnosis (WHO CNS5):** Extraventricular neurocytoma  
* **Taxonomic Group:** Gliomas... / Glioneuronal and neuronal tumors  
* **Previous Designation(s):** Extraventricular neurocytoma (WHO 2016).  
* **CNS WHO Grade:** 2\.  
* **Key Demographics & Location:** Same as central neurocytoma but located in the brain parenchyma ("extraventricular").1  
* **Histological Features:** Same histology as central neurocytoma.  
* **Characteristic Molecular Features (Supportive):** $FGFR$ alterations (e.g., $FGFR1-TACC1$ fusion) are characteristic. $IDH$ is wildtype.1  
* **Source Reference(s):** 1

##### **Cerebellar liponeurocytoma**

* **Diagnosis (WHO CNS5):** Cerebellar liponeurocytoma  
* **Taxonomic Group:** Gliomas... / Glioneuronal and neuronal tumors  
* **Previous Designation(s):** Same (WHO 2016).  
* **CNS WHO Grade:** 2\.  
* **Key Demographics & Location:** Adults. Located in the cerebellum.  
* **Histological Features:** Neurocytic tumor with "lipomatous" (fat) differentiation (lipid-filled vacuoles).  
* **Source Reference(s):** 1

#### **Ependymal tumors**

Ependymoma classification is now based on a combination of location, histology, and molecular features.1 The histological term "anaplastic ependymoma" is no longer a distinct type but rather represents CNS WHO grade 3, which is applied *within* the new molecular types.1

##### **Supratentorial ependymoma**

* **Diagnosis (WHO CNS5):** Supratentorial ependymoma  
* **Taxonomic Group:** Gliomas... / Ependymal tumors  
* **Previous Designation(s):** N/A. This is a location-based diagnosis used when molecular testing is not available (NOS) or not definitive (NEC).1  
* **CNS WHO Grade:** 2 or 3 (based on histological features).1  
* **Key Demographics & Location:** Supratentorial compartment.  
* **Histological Features:** Ependymoma histology (perivascular pseudorosettes, true ependymal rosettes). Can be histologically Grade 2 or Grade 3 ("anaplastic").1  
* **Essential Molecular Features (Definitional):** Absence of $ZFTA$ or $YAP1$ fusions.  
* **Source Reference(s):** 1

##### **Supratentorial ependymoma, ZFTA fusion-positive**

* **Diagnosis (WHO CNS5):** Supratentorial ependymoma, ZFTA fusion-positive  
* **Taxonomic Group:** Gliomas... / Ependymal tumors  
* **Previous Designation(s):** Supratentorial Ependymoma, RELA fusion-positive (WHO 2016).1 The name was changed to $ZFTA$ (the new name for $C11orf95$) as it is the more representative fusion partner.1  
* **CNS WHO Grade:** 2 or 3\.1  
* **Key Demographics & Location:** Supratentorial compartment.  
* **Histological Features:** Ependymoma histology.  
* **Essential Molecular Features (Definitional):** A fusion involving the $ZFTA$ gene, most commonly $ZFTA-RELA$. Other $ZFTA$ partners are also included.1  
* **Source Reference(s):** 1

##### **Supratentorial ependymoma, YAP1 fusion-positive**

* **Diagnosis (WHO CNS5):** Supratentorial ependymoma, YAP1 fusion-positive  
* **Taxonomic Group:** Gliomas... / Ependymal tumors  
* **Previous Designation(s):** Newly recognized type.1  
* **CNS WHO Grade:** N/A from source (likely 2 or 3).1  
* **Key Demographics & Location:** Supratentorial compartment.  
* **Histological Features:** Ependymoma histology.  
* **Essential Molecular Features (Definitional):** A fusion involving the $YAP1$ gene (e.g., $YAP1-MAML2$).1  
* **Source Reference(s):** 1

##### **Posterior fossa ependymoma**

* **Diagnosis (WHO CNS5):** Posterior fossa ependymoma  
* **Taxonomic Group:** Gliomas... / Ependymal tumors  
* **Previous Designation(s):** N/A. This is a location-based diagnosis used when molecular testing is not available (NOS) or not definitive (NEC).1  
* **CNS WHO Grade:** 2 or 3 (based on histological features).1  
* **Key Demographics & Location:** Posterior fossa.  
* **Histological Features:** Ependymoma histology. Can be histologically Grade 2 or Grade 3 ("anaplastic").1  
* **Essential Molecular Features (Definitional):** Absence of PFA or PFB methylation profile.  
* **Source Reference(s):** 1

##### **Posterior fossa ependymoma, group PFA**

* **Diagnosis (WHO CNS5):** Posterior fossa ependymoma, group PFA  
* **Taxonomic Group:** Gliomas... / Ependymal tumors  
* **Previous Designation(s):** Newly recognized type.1  
* **CNS WHO Grade:** 2 or 3\.1  
* **Key Demographics & Location:** Posterior fossa. Predominantly affects very young children and has a worse prognosis.  
* **Histological Features:** Ependymoma histology.  
* **Essential Molecular Features (Definitional):** Defined by a characteristic DNA methylation profile ("group PFA").1  
* **Characteristic Molecular Features (Supportive):** Characterized by *loss* of H3 K27 trimethylation (H3 K27me3) via an epigenetic mechanism (not mutation) or, in some cases, $EZHIP$ overexpression.1  
* **Source Reference(s):** 1

##### **Posterior fossa ependymoma, group PFB**

* **Diagnosis (WHO CNS5):** Posterior fossa ependymoma, group PFB  
* **Taxonomic Group:** Gliomas... / Ependymal tumors  
* **Previous Designation(s):** Newly recognized type.1  
* **CNS WHO Grade:** 2 or 3\.1  
* **Key Demographics & Location:** Posterior fossa. Tends to occur in older children and adults and has a better prognosis than PFA.  
* **Histological Features:** Ependymoma histology.  
* **Essential Molecular Features (Definitional):** Defined by a characteristic DNA methylation profile ("group PFB").1  
* **Characteristic Molecular Features (Supportive):** H3 K27me3 is *retained* (unlike PFA).1  
* **Source Reference(s):** 1

##### **Spinal ependymoma**

* **Diagnosis (WHO CNS5):** Spinal ependymoma  
* **Taxonomic Group:** Gliomas... / Ependymal tumors  
* **Previous Designation(s):** N/A. This is a location-based diagnosis used when molecular testing is not available (NOS) or not definitive (NEC).1  
* **CNS WHO Grade:** 2 or 3 (based on histological features).  
* **Key Demographics & Location:** Spinal compartment.  
* **Histological Features:** Ependymoma histology.  
* **Characteristic Molecular Features (Supportive):** Most are $NF2$-mutated.1  
* **Source Reference(s):** 1

##### **Spinal ependymoma, MYCN-amplified**

* **Diagnosis (WHO CNS5):** Spinal ependymoma, MYCN-amplified  
* **Taxonomic Group:** Gliomas... / Ependymal tumors  
* **Previous Designation(s):** Newly recognized type.1  
* **CNS WHO Grade:** N/A from source (implied high-grade).  
* **Key Demographics & Location:** Spinal compartment.  
* **Histological Features:** Ependymoma histology, but often high-grade.  
* **Essential Molecular Features (Definitional):** $MYCN$ gene amplification.1  
* **Source Reference(s):** 1

##### **Myxopapillary ependymoma**

* **Diagnosis (WHO CNS5):** Myxopapillary ependymoma  
* **Taxonomic Group:** Gliomas... / Ependymal tumors  
* **Previous Designation(s):** Myxopapillary ependymoma (WHO 2016).  
* **CNS WHO Grade:** 2\.1 This is a significant change; it was Grade 1 in 2016\. It is now considered Grade 2 due to its higher likelihood of recurrence, similar to conventional spinal ependymoma.1  
* **Key Demographics & Location:** Almost exclusively in the spinal cord, particularly the cauda equina and filum terminale.1  
* **Histological Features:** Papillary structures set within a prominent myxoid (mucinous) stroma.1  
* **Essential Molecular Features (Definitional):** Histology and location are definitional.  
* **Source Reference(s):** 1

##### **Subependymoma**

* **Diagnosis (WHO CNS5):** Subependymoma  
* **Taxonomic Group:** Gliomas... / Ependymal tumors  
* **Previous Designation(s):** Subependymoma (WHO 2016).  
* **CNS WHO Grade:** 1\.  
* **Key Demographics & Location:** Adults. Intraventricular, often 4th ventricle or lateral ventricles, attached to the ventricular lining (subependymal).  
* **Histological Features:** Benign, slow-growing. Lobulated, paucicellular (low cell density) tumor with clusters of cells in a dense fibrillary (glial) matrix.  
* **Source Reference(s):** 1

### **2.2 Choroid Plexus Tumors**

This family is now separated from gliomas due to its distinct epithelial differentiation.1 The classification remains largely unchanged.

##### **Choroid plexus papilloma**

* **Diagnosis (WHO CNS5):** Choroid plexus papilloma  
* **Taxonomic Group:** Choroid plexus tumors  
* **Previous Designation(s):** Choroid plexus papilloma (WHO 2016).  
* **CNS WHO Grade:** 1\.  
* **Key Demographics & Location:** Primarily children. Located intraventricularly.  
* **Histological Features:** Benign, papillary tumor that closely resembles normal choroid plexus.1  
* **Source Reference(s):** 1

##### **Atypical choroid plexus papilloma**

* **Diagnosis (WHO CNS5):** Atypical choroid plexus papilloma  
* **Taxonomic Group:** Choroid plexus tumors  
* **Previous Designation(s):** Atypical choroid plexus papilloma (WHO 2016).  
* **CNS WHO Grade:** 2\.  
* **Key Demographics & Location:** Primarily children. Located intraventricularly.  
* **Histological Features:** Shows increased mitotic activity and/or other features (increased cellularity, nuclear pleomorphism, loss of architecture) compared to the papilloma.1  
* **Source Reference(s):** 1

##### **Choroid plexus carcinoma**

* **Diagnosis (WHO CNS5):** Choroid plexus carcinoma  
* **Taxonomic Group:** Choroid plexus tumors  
* **Previous Designation(s):** Choroid plexus carcinoma (WHO 2016).  
* **CNS WHO Grade:** 3\.  
* **Key Demographics & Location:** Primarily young children. Located intraventricularly.  
* **Histological Features:** Frankly malignant, epithelial tumor with loss of papillary architecture, high mitotic activity, necrosis, and brain invasion.  
* **Characteristic Molecular Features (Supportive):** $TP53$ mutation is common (can be germline, Li-Fraumeni syndrome). Loss of $SMARCB1$ (INI1) expression can occur, creating a differential diagnosis with AT/RT \[1, p. 17, Table 2 (AT/RT)\].  
* **Source Reference(s):** 1

### **2.3 Embryonal Tumors**

This category includes the medulloblastomas and other highly malignant, undifferentiated tumors that typically affect children.1

#### **Medulloblastomas**

The classification of medulloblastoma is now primarily molecular. The four principal molecular groups (WNT, SHH, Group 3, Group 4\) are the basis for the diagnosis. Histological types (Classic, Desmoplastic/Nodular, MBEN, Large Cell/Anaplastic) are now considered "patterns" or subtypes that are strongly associated with, but do not define, the molecular groups.1 All medulloblastomas are, by definition, CNS WHO Grade 4\.1

##### **Medulloblastoma, WNT-activated**

* **Diagnosis (WHO CNS5):** Medulloblastoma, WNT-activated  
* **Taxonomic Group:** Embryonal tumors / Medulloblastomas, molecularly defined  
* **Previous Designation(s):** Medulloblastoma, WNT-activated (WHO 2016).  
* **CNS WHO Grade:** 4\. (Note: Despite being Grade 4, this type has an *excellent* prognosis with standard therapy 1).  
* **Key Demographics & Location:** Children and adults. Typically midline (cerebellum/4th ventricle).  
* **Histological Features:** Almost always has "classic" medulloblastoma histology (dense, a-vascular sheets of small round blue cells with high N:C ratio).1  
* **Essential Molecular Features (Definitional):** Activation of the WNT signaling pathway, most commonly via a mutation in $CTNNB1$ (beta-catenin). This is confirmed by nuclear accumulation of beta-catenin on immunohistochemistry (IHC).1  
* **Characteristic Molecular Features (Supportive):** Monosomy 6 is common. $APC$ germline mutation (Turcot syndrome) can be the cause.1  
* **Source Reference(s):** 1

##### **Medulloblastoma, SHH-activated and TP53-wildtype**

* **Diagnosis (WHO CNS5):** Medulloblastoma, SHH-activated and TP53-wildtype  
* **Taxonomic Group:** Embryonal tumors / Medulloblastomas, molecularly defined  
* **Previous Designation(s):** Medulloblastoma, SHH-activated (WHO 2016\) \[in part\]. The 2021 classification *mandates* splitting SHH tumors by $TP53$ status.1  
* **CNS WHO Grade:** 4\.  
* **Key Demographics & Location:** Bimodal age distribution: Infants (\<3 years) and adults. Typically located in the cerebellar hemispheres (lateral).1  
* **Histological Features:** Often shows "desmoplastic/nodular" histology or "medulloblastoma with extensive nodularity (MBEN)" histology, particularly in infants.1  
* **Essential Molecular Features (Definitional):** Activation of the Sonic Hedgehog (SHH) signaling pathway *AND* wildtype $TP53$ status.1  
* **Characteristic Molecular Features (Supportive):** SHH pathway activation is often driven by mutations in $PTCH1$, $SUFU$ (germinoma \= Gorlin syndrome), or $SMO$. $MYCN$ or $GLI2$ amplification can occur.1  
* **Source Reference(s):** 1

##### **Medulloblastoma, SHH-activated and TP53-mutant**

* **Diagnosis (WHO CNS5):** Medulloblastoma, SHH-activated and TP53-mutant  
* **Taxonomic Group:** Embryonal tumors / Medulloblastomas, molecularly defined  
* **Previous Designation(s):** Medulloblastoma, SHH-activated (WHO 2016\) \[in part\]. This is a newly separated, distinct type.1  
* **CNS WHO Grade:** 4\. (Note: This type has a *very poor* prognosis).  
* **Key Demographics & Location:** Occurs in older children.  
* **Histological Features:** Often shows "large cell / anaplastic (LCA)" histology.1  
* **Essential Molecular Features (Definitional):** Activation of the SHH signaling pathway *AND* the presence of a $TP53$ mutation (somatic or germline, e.g., Li-Fraumeni syndrome).1  
* **Characteristic Molecular Features (Supportive):** See SHH-wildtype.  
* **Source Reference(s):** 1

##### **Medulloblastoma, non-WNT/non-SHH**

* **Diagnosis (WHO CNS5):** Medulloblastoma, non-WNT/non-SHH  
* **Taxonomic Group:** Embryonal tumors / Medulloblastomas, molecularly defined  
* **Previous Designation(s):** This category encompasses the former "Group 3" and "Group 4" medulloblastomas.1  
* **CNS WHO Grade:** 4\.  
* **Key Demographics & Location:** Primarily children. Typically midline (cerebellum/4th ventricle).  
* **Histological Features:** Most often "classic" or "large cell / anaplastic (LCA)" histology.1  
* **Essential Molecular Features (Definitional):** This is a diagnosis of exclusion. It is defined by the *absence* of WNT or SHH pathway activation.1  
* **Characteristic Molecular Features (Supportive):** This group is heterogeneous. $MYC$ amplification is a key finding (defines "Group 3" and confers a very poor prognosis). $MYCN$ amplification and $KDM6A$ mutations are also seen. DNA methylation profiling can separate this into 8 distinct subgroups.1  
* **Source Reference(s):** 1

##### **Medulloblastomas, histologically defined**

* **Diagnosis (WHO CNS5):** Medulloblastomas, histologically defined  
* **Taxonomic Group:** Embryonal tumors / Medulloblastomas  
* **Previous Designation(s):** N/A. This is a classification to be used when molecular subtyping is not possible (i.e., this is the "NOS" category for medulloblastoma).  
* **CNS WHO Grade:** 4\.  
* **Key Demographics & Location:** N/A.  
* **Histological Features:** Histological diagnosis of medulloblastoma (classic, desmoplastic/nodular, MBEN, or LCA) without any molecular data.  
* **Source Reference(s):** 1

#### **Other CNS embryonal tumors**

This group includes highly malignant embryonal tumors that are not medulloblastoma.1

##### **Atypical teratoid/rhabdoid tumor (AT/RT)**

* **Diagnosis (WHO CNS5):** Atypical teratoid/rhabdoid tumor  
* **Taxonomic Group:** Embryonal tumors / Other CNS embryonal tumors  
* **Previous Designation(s):** AT/RT (WHO 2016).  
* **CNS WHO Grade:** 4\.  
* **Key Demographics & Location:** Very young children (infants and toddlers). Can occur anywhere in the CNS (supratentorial or posterior fossa).  
* **Histological Features:** Highly malignant, "small round blue cell" tumor with characteristic "rhabdoid" cells (large cells with eccentric nuclei and glassy, eosinophilic cytoplasm).  
* **Essential Molecular Features (Definitional):** Inactivation (by mutation or deletion) of a core SWI/SNF complex gene. This is almost always $SMARCB1$ (also known as $INI1$ or $BAF47$) or, very rarely, $SMARCA4$ (also known as $BRG1$).1 Diagnosis is typically made by IHC showing *loss* of nuclear staining for INI1 or BRG1.  
* **Characteristic Molecular Features (Supportive):** Three molecular subtypes (AT/RT-SHH, AT/RT-TYR, AT/RT-MYC) are recognized.1  
* **Source Reference(s):** 1

##### **Cribriform neuroepithelial tumor**

* **Diagnosis (WHO CNS5):** Cribriform neuroepithelial tumor  
* **Taxonomic Group:** Embryonal tumors / Other CNS embryonal tumors  
* **Previous Designation(s):** Newly recognized provisional type.1  
* **CNS WHO Grade:** N/A from source.  
* **Key Demographics & Location:** N/A from source.  
* **Histological Features:** "Cribriform" (sieve-like) architecture.  
* **Source Reference(s):** 1

##### **Embryonal tumor with multilayered rosettes (ETMR)**

* **Diagnosis (WHO CNS5):** Embryonal tumor with multilayered rosettes  
* **Taxonomic Group:** Embryonal tumors / Other CNS embryonal tumors  
* **Previous Designation(s):** ETMR, C19MC-altered (WHO 2016). The genetic modifier was removed from the *name* to allow for the inclusion of new genetic subtypes.1  
* **CNS WHO Grade:** 4\.  
* **Key Demographics & Location:** Very young children (infants).  
* **Histological Features:** Primitive neuroepithelial tumor characterized by pathognomonic "multilayered rosettes".1  
* **Essential Molecular Features (Definitional):** Most cases are defined by amplification of the $C19MC$ microRNA cluster. A new, distinct subtype is defined by $DICER1$ mutation.1  
* **Source Reference(s):** 1

##### **CNS neuroblastoma, FOXR2-activated**

* **Diagnosis (WHO CNS5):** CNS neuroblastoma, FOXR2-activated  
* **Taxonomic Group:** Embryonal tumors / Other CNS embryonal tumors  
* **Previous Designation(s):** Newly recognized type.1  
* **CNS WHO Grade:** 4\.  
* **Key Demographics & Location:** N/A from source.  
* **Histological Features:** Neuroblastoma histology (small round blue cells, Homer-Wright rosettes).  
* **Essential Molecular Features (Definitional):** Activation of the $FOXR2$ gene.1  
* **Source Reference(s):** 1

##### **CNS tumor with BCOR internal tandem duplication**

* **Diagnosis (WHO CNS5):** CNS tumor with BCOR internal tandem duplication  
* **Taxonomic Group:** Embryonal tumors / Other CNS embryonal tumors  
* **Previous Designation(s):** Newly recognized type.1  
* **CNS WHO Grade:** 4\.  
* **Key Demographics & Location:** N/A from source.  
* **Histological Features:** High-grade neoplasm with a mostly solid growth pattern, uniform cells, a dense capillary network, and focal perivascular pseudorosettes. Shows strong, diffuse nuclear staining on BCOR IHC.1  
* **Essential Molecular Features (Definitional):** An internal tandem duplication (ITD) in exon 15 of the $BCOR$ gene.1  
* **Source Reference(s):** 1

##### **CNS embryonal tumor**

* **Diagnosis (WHO CNS5):** CNS embryonal tumor  
* **Taxonomic Group:** Embryonal tumors / Other CNS embryonal tumors  
* **Previous Designation(s):** CNS embryonal tumor, NOS; PNET.  
* **CNS WHO Grade:** 4\.  
* **Key Demographics & Location:** N/A.  
* **Histological Features:** A "catch-all" diagnosis for any embryonal tumor that cannot be classified into one of the specific types listed above. This is the "NOS" or "NEC" diagnosis for this family.1  
* **Source Reference(s):** 1

### **2.4 Pineal Tumors**

This family includes tumors arising from the pineal gland parenchyma or other elements in the pineal region.1

##### **Pineocytoma**

* **Diagnosis (WHO CNS5):** Pineocytoma  
* **Taxonomic Group:** Pineal tumors  
* **Previous Designation(s):** Pineocytoma (WHO 2016).  
* **CNS WHO Grade:** 1\.  
* **Key Demographics & Location:** Adults. Located in the pineal gland.  
* **Histological Features:** Benign, slow-growing. Composed of mature, uniform pineocyte-like cells forming "pineocytomatous rosettes" (large, unstructured rosettes).  
* **Source Reference(s):** 1

##### **Pineal parenchymal tumor of intermediate differentiation (PPTID)**

* **Diagnosis (WHO CNS5):** Pineal parenchymal tumor of intermediate differentiation  
* **Taxonomic Group:** Pineal tumors  
* **Previous Designation(s):** PPTID (WHO 2016).  
* **CNS WHO Grade:** 2 or 3 (behavior is intermediate).  
* **Key Demographics & Location:** Adults. Located in the pineal gland.  
* **Histological Features:** Histological features are intermediate between the benign pineocytoma and the malignant pineoblastoma.  
* **Source Reference(s):** 1

##### **Pineoblastoma**

* **Diagnosis (WHO CNS5):** Pineoblastoma  
* **Taxonomic Group:** Pineal tumors  
* **Previous Designation(s):** Pineoblastoma (WHO 2016).  
* **CNS WHO Grade:** 4\.  
* **Key Demographics & Location:** Primarily children. Located in the pineal gland. Associated with germline $RB1$ mutations (trilateral retinoblastoma).  
* **Histological Features:** Highly malignant, "small round blue cell" embryonal tumor.  
* **Characteristic Molecular Features (Supportive):** DNA methylation profiling divides pineoblastoma into several subtypes, including those with $DICER1$, $DROSHA$, or $DGCR8$ mutations, $MYC$ or $FOXR2$ activation, or $RB1$ alterations.1  
* **Source Reference(s):** 1

##### **Papillary tumor of the pineal region**

* **Diagnosis (WHO CNS5):** Papillary tumor of the pineal region (PTPR)  
* **Taxonomic Group:** Pineal tumors  
* **Previous Designation(s):** PTPR (WHO 2016).  
* **CNS WHO Grade:** 2 or 3\.  
* **Key Demographics & Location:** Adults. Located in the pineal region.  
* **Histological Features:** Papillary architecture. Arises from the ependymal cells of the subcommissural organ.  
* **Source Reference(s):** 1

##### **Desmoplastic myxoid tumor of the pineal region, SMARCB1-mutant**

* **Diagnosis (WHO CNS5):** Desmoplastic myxoid tumor of the pineal region, SMARCB1-mutant  
* **Taxonomic Group:** Pineal tumors  
* **Previous Designation(s):** Newly recognized type.1  
* **CNS WHO Grade:** N/A from source (grading criteria not yet defined).1  
* **Key Demographics & Location:** Adolescents and adults. Located in the pineal region.1  
* **Histological Features:** Rare tumor lacking histological signs of malignancy. Features "desmoplasia" (fibrosis) and prominent "myxoid" changes.1  
* **Essential Molecular Features (Definitional):** $SMARCB1$ mutation.1 This results in *loss* of nuclear INI1 staining on IHC, creating a critical differential diagnosis with AT/RT.1  
* **Source Reference(s):** 1

### **2.5 Cranial and Paraspinal Nerve Tumors**

This family includes tumors of the peripheral nerves, their sheath cells, and paraganglia.1

##### **Schwannoma**

* **Diagnosis (WHO CNS5):** Schwannoma  
* **Taxonomic Group:** Cranial and paraspinal nerve tumors  
* **Previous Designation(s):** Schwannoma (WHO 2016).  
* **CNS WHO Grade:** 1\.  
* **Key Demographics & Location:** Adults. Most common is vestibular schwannoma (acoustic neuroma). Associated with $NF2$ germline mutation (Neurofibromatosis type 2).  
* **Histological Features:** Benign, encapsulated tumor. Biphasic: "Antoni A" (dense, spindle cells, Verocay bodies) and "Antoni B" (loose, myxoid). Strong, diffuse S100 protein positivity.  
* **Essential Molecular Features (Definitional):** Inactivation of $NF2$ (e.g., $NF2$ mutation).  
* **Source Reference(s):** 1

##### **Neurofibroma**

* **Diagnosis (WHO CNS5):** Neurofibroma  
* **Taxonomic Group:** Cranial and paraspinal nerve tumors  
* **Previous Designation(s):** Neurofibroma (WHO 2016).  
* **CNS WHO Grade:** 1\.  
* **Key Demographics & Location:** Associated with $NF1$ germline mutation (Neurofibromatosis type 1). Can be cutaneous, intraneural, or plexiform.  
* **Histological Features:** Unencapsulated, benign. Composed of a mix of Schwann cells, perineurial-like cells, and fibroblasts in a myxoid stroma.  
* **Essential Molecular Features (Definitional):** Inactivation of $NF1$.  
* **Source Reference(s):** 1

##### **Perineurioma**

* **Diagnosis (WHO CNS5):** Perineurioma  
* **Taxonomic Group:** Cranial and paraspinal nerve tumors  
* **Previous Designation(s):** Perineurioma (WHO 2016).  
* **CNS WHO Grade:** 1\.  
* **Key Demographics & Location:** N/A from source.  
* **Histological Features:** Benign. Composed of bland, spindle cells with "whorled" growth, resembling perineurial cells. EMA positive, S100 negative.  
* **Source Reference(s):** 1

##### **Hybrid nerve sheath tumor**

* **Diagnosis (WHO CNS5):** Hybrid nerve sheath tumor  
* **Taxonomic Group:** Cranial and paraspinal nerve tumors  
* **Previous Designation(s):** N/A from source.  
* **CNS WHO Grade:** 1\.  
* **Key Demographics & Location:** N/A from source.  
* **Histological Features:** Benign tumor with combined features of schwannoma, neurofibroma, and/or perineurioma.  
* **Source Reference(s):** 1

##### **Malignant melanotic nerve sheath tumor**

* **Diagnosis (WHO CNS5):** Malignant melanotic nerve sheath tumor  
* **Taxonomic Group:** Cranial and paraspinal nerve tumors  
* **Previous Designation(s):** Melanotic schwannoma (WHO 2016).1  
* **CNS WHO Grade:** High-grade (malignant).  
* **Key Demographics & Location:** N/A from source.  
* **Histological Features:** A nerve sheath tumor that produces melanin pigment.  
* **Essential Molecular Features (Definitional):** The name was changed to reflect its aggressive behavior and unique genetic underpinnings (distinct from schwannoma).1  
* **Source Reference(s):** 1

##### **Malignant peripheral nerve sheath tumor (MPNST)**

* **Diagnosis (WHO CNS5):** Malignant peripheral nerve sheath tumor  
* **Taxonomic Group:** Cranial and paraspinal nerve tumors  
* **Previous Designation(s):** MPNST (WHO 2016).  
* **CNS WHO Grade:** 3 or 4\.  
* **Key Demographics & Location:** Can arise *de novo* or from a pre-existing neurofibroma, especially in $NF1$ patients.  
* **Histological Features:** Malignant spindle cell sarcoma arising from a nerve.  
* **Source Reference(s):** 1

##### **Paraganglioma**

* **Diagnosis (WHO CNS5):** Paraganglioma  
* **Taxonomic Group:** Cranial and paraspinal nerve tumors  
* **Previous Designation(s):** Paraganglioma (WHO 2016).  
* **CNS WHO Grade:** N/A from source (behavior is variable).  
* **Key Demographics & Location:** Arise from paraganglia (neuroendocrine cells). In the CNS, often at the skull base (e.g., glomus jugulare) or cauda equina/filum terminale.  
* **Histological Features:** Neuroendocrine tumor. "Zellballen" (cell nests) of chief cells surrounded by S100-positive sustentacular cells.  
* **Source Reference(s):** 1

### **2.6 Meningiomas**

The classification of meningiomas has been simplified into a single type, with grading and subtypes applied within that type.1

##### **Meningioma**

* **Diagnosis (WHO CNS5):** Meningioma  
* **Taxonomic Group:** Meningiomas  
* **Previous Designation(s):** Meningioma (WHO 2016, Grade 1); Atypical Meningioma (WHO 2016, Grade 2); Anaplastic (Malignant) Meningioma (WHO 2016, Grade 3).1  
* **CNS WHO Grade:** 1, 2, or 3\.1 Grading is based on histological criteria (e.g., mitotic count, brain invasion) OR molecular criteria.  
* **Key Demographics & Location:** Primarily adults, female predominance. Arise from the meninges (dura mater).  
* **Histological Features:** A single type with 15 histological *subtypes* (e.g., meningothelial, fibrous, transitional, psammomatous, secretory, etc.).1  
  * **Subtypes that are automatically Grade 2:** Chordoid and Clear Cell.1  
  * **Subtypes associated with Grade 3:** Rhabdoid and Papillary morphology are associated with aggressive behavior but are no longer automatically Grade 3 based on morphology alone.1  
* **Characteristic Molecular Features (Supportive):**  
  * **General:** $NF2$ mutation is the most common driver (associated with fibrous/transitional subtypes).  
  * **Non-NF2:** Tumors are often driven by $AKT1$, $TRAF7$, $SMO$, or $PIK3CA$ mutations.1  
  * **Subtype-Specific:** $KLF4/TRAF7$ (Secretory subtype), $SMARCE1$ (Clear Cell subtype), $BAP1$ (Rhabdoid and Papillary subtypes).1  
* **Molecular Grading Markers:**  
  * **Grade 3:** $TERT$ promoter mutation *OR* $CDKN2A/B$ homozygous deletion automatically confers CNS WHO Grade 3, *regardless* of histological features.1  
  * **Prognostic:** Loss of nuclear expression of $H3K27me3$ is associated with a worse prognosis.1  
* **Source Reference(s):** 1

### **2.7 Mesenchymal, Non-Meningothelial Tumors**

This category is now aligned with the WHO Classification of Soft Tissue Tumors. Tumors common in soft tissue that are rare in the CNS (e.g., leiomyoma) have been removed. The term "hemangiopericytoma" is officially retired.1

#### **Soft tissue tumors**

##### **Solitary fibrous tumor**

* **Diagnosis (WHO CNS5):** Solitary fibrous tumor  
* **Taxonomic Group:** Mesenchymal... / Soft tissue tumors / Fibroblastic...  
* **Previous Designation(s):** Solitary fibrous tumor / Hemangiopericytoma (WHO 2016).1 The term "Hemangiopericytoma" (HPC) is now obsolete and should be mapped to this diagnosis.1  
* **CNS WHO Grade:** 1, 2, or 3\.1 This is a CNS-specific, 3-tiered grading scheme.1  
* **Key Demographics & Location:** Adults. Dura-based, often mimicking meningioma.  
* **Histological Features:** Spindle cell tumor with a "patternless" pattern and characteristic "staghorn" branching vessels.  
* **Essential Molecular Features (Definitional):** A $NAB2-STAT6$ gene fusion.1 This is diagnosed by strong, diffuse nuclear STAT6 positivity on IHC.  
* **Source Reference(s):** 1

##### **Hemangioblastoma**

* **Diagnosis (WHO CNS5):** Hemangioblastoma  
* **Taxonomic Group:** Mesenchymal... / Soft tissue tumors / Vascular tumors  
* **Previous Designation(s):** Hemangioblastoma (WHO 2016).  
* **CNS WHO Grade:** 1\.  
* **Key Demographics & Location:** Adults. Associated with von Hippel-Lindau (VHL) syndrome. Classically in the cerebellum, brainstem, or spinal cord.  
* **Histological Features:** Highly vascular tumor. Composed of (1) thin-walled capillaries and (2) large, lipid-laden "stromal cells" which are the true neoplastic cells.  
* **Essential Molecular Features (Definitional):** Inactivation of the $VHL$ gene.  
* **Source Reference(s):** 1

##### **Rhabdomyosarcoma**

* **Diagnosis (WHO CNS5):** Rhabdomyosarcoma  
* **Taxonomic Group:** Mesenchymal... / Soft tissue tumors / Skeletal muscle tumors  
* **Previous Designation(s):** Rhabdomyosarcoma (WHO 2016).  
* **CNS WHO Grade:** 4\.  
* **Key Demographics & Location:** Primarily pediatric.  
* **Histological Features:** Malignant tumor with skeletal muscle differentiation (rhabdomyoblasts). Subtypes include embryonal (ERMS) and alveolar (ARMS).  
* **Characteristic Molecular Features (Supportive):** ARMS is defined by $FOXO1$ fusions (e.g., $PAX3-FOXO1$, $PAX7-FOXO1$).  
* **Source Reference(s):** 1

##### **Intracranial mesenchymal tumor, FET-CREB fusion-positive**

* **Diagnosis (WHO CNS5):** Intracranial mesenchymal tumor, FET-CREB fusion-positive  
* **Taxonomic Group:** Mesenchymal... / Soft tissue tumors / Uncertain differentiation  
* **Previous Designation(s):** Newly recognized provisional type.1  
* **CNS WHO Grade:** N/A from source.  
* **Key Demographics & Location:** N/A from source.  
* **Histological Features:** Mesenchymal tumor with variable morphology.1  
* **Essential Molecular Features (Definitional):** A fusion of a $FET$ family gene ($FUS$, $EWSR1$, $TAF15$) and a $CREB$ family transcription factor ($ATF1$, $CREB1$, $CREM$).1  
* **Source Reference(s):** 1

##### **CIC-rearranged sarcoma**

* **Diagnosis (WHO CNS5):** CIC-rearranged sarcoma  
* **Taxonomic Group:** Mesenchymal... / Soft tissue tumors / Uncertain differentiation  
* **Previous Designation(s):** Newly recognized type.1  
* **CNS WHO Grade:** 4\.  
* **Key Demographics & Location:** N/A from source.  
* **Histological Features:** Poorly differentiated "small round blue cell" sarcoma.1 ETV4 is frequently upregulated.1  
* **Essential Molecular Features (Definitional):** A fusion involving the $CIC$ gene (e.g., $CIC-DUX4$).  
* **Source Reference(s):** 1

##### **Primary intracranial sarcoma, DICER1-mutant**

* **Diagnosis (WHO CNS5):** Primary intracranial sarcoma, DICER1-mutant  
* **Taxonomic Group:** Mesenchymal... / Soft tissue tumors / Uncertain differentiation  
* **Previous Designation(s):** Newly recognized type.1  
* **CNS WHO Grade:** 4\.  
* **Key Demographics & Location:** Associated with $DICER1$ tumor predisposition syndrome.  
* **Histological Features:** Sarcoma with characteristic eosinophilic cytoplasmic droplets.1  
* **Essential Molecular Features (Definitional):** $DICER1$ mutation.1  
* **Source Reference(s):** 1

##### **Ewing sarcoma**

* **Diagnosis (WHO CNS5):** Ewing sarcoma  
* **Taxonomic Group:** Mesenchymal... / Soft tissue tumors / Uncertain differentiation  
* **Previous Designation(s):** Ewing sarcoma (WHO 2016).  
* **CNS WHO Grade:** 4\.  
* **Key Demographics & Location:** Primarily pediatric/young adult.  
* **Histological Features:** "Small round blue cell" tumor.  
* **Essential Molecular Features (Definitional):** A $FET$ family fusion, most commonly $EWSR1-FLI1$.  
* **Source Reference(s):** 1

#### **Chondro-osseous tumors**

##### **Mesenchymal chondrosarcoma**

* **Diagnosis (WHO CNS5):** Mesenchymal chondrosarcoma  
* **Taxonomic Group:** Mesenchymal... / Chondro-osseous tumors / Chondrogenic...  
* **Previous Designation(s):** Previously a *subtype* of Chondrosarcoma, now a distinct *type*.1  
* **CNS WHO Grade:** 4\.  
* **Key Demographics & Location:** N/A from source.  
* **Histological Features:** Biphasic tumor with (1) islands of well-differentiated cartilage and (2) undifferentiated "small round blue cells."  
* **Characteristic Molecular Features (Supportive):** $HEY1-NCOA2$ fusion is characteristic.  
* **Source Reference(s):** 1

##### **Chondrosarcoma**

* **Diagnosis (WHO CNS5):** Chondrosarcoma  
* **Taxonomic Group:** Mesenchymal... / Chondro-osseous tumors / Chondrogenic...  
* **Previous Designation(s):** Chondrosarcoma (WHO 2016).  
* **CNS WHO Grade:** 1, 2, or 3 (variable).  
* **Key Demographics & Location:** Skull base.  
* **Histological Features:** Malignant tumor composed of neoplastic cartilage.  
* **Characteristic Molecular Features (Supportive):** $IDH1$ or $IDH2$ mutations are common (but different from glioma mutations).  
* **Source Reference(s):** 1

##### **Chordoma**

* **Diagnosis (WHO CNS5):** Chordoma (including poorly differentiated chordoma)  
* **Taxonomic Group:** Mesenchymal... / Chondro-osseous tumors / Notochordal...  
* **Previous Designation(s):** Chordoma (WHO 2016).  
* **CNS WHO Grade:** N/A from source (locally aggressive, malignant).  
* **Key Demographics & Location:** Arises from notochordal remnants. In the CNS, primarily at the skull base (clivus) or sacrum.  
* **Histological Features:** Classic "physaliphorous" cells (large, vacuolated, "bubble-wrap" cells) in a myxoid stroma.  
* **Essential Molecular Features (Definitional):** Nuclear expression of Brachyury ($TBXT$) is the defining diagnostic marker. Poorly differentiated chordoma is characterized by loss of $SMARCB1$ (INI1).  
* **Source Reference(s):** 1

### **2.8 Melanocytic Tumors**

These tumors arise from melanocytes in the leptomeninges.

##### **Meningeal melanocytosis and meningeal melanomatosis**

* **Diagnosis (WHO CNS5):** Meningeal melanocytosis / meningeal melanomatosis  
* **Taxonomic Group:** Melanocytic tumors / Diffuse meningeal melanocytic neoplasms  
* **Previous Designation(s):** Same (WHO 2016).  
* **CNS WHO Grade:** Melanocytosis (low-grade), Melanomatosis (high-grade).  
* **Key Demographics & Location:** Diffuse spread throughout the leptomeninges.  
* **Histological Features:** Proliferation of melanocytes (benign or malignant) within the meninges.  
* **Characteristic Molecular Features (Supportive):** $NRAS$ mutations are common.1  
* **Source Reference(s):** 1

##### **Meningeal melanocytoma and meningeal melanoma**

* **Diagnosis (WHO CNS5):** Meningeal melanocytoma / meningeal melanoma  
* **Taxonomic Group:** Melanocytic tumors / Circumscribed meningeal melanocytic neoplasms  
* **Previous Designation(s):** Same (WHO 2016).  
* **CNS WHO Grade:** Melanocytoma (low-grade), Melanoma (high-grade).  
* **Key Demographics & Location:** A discrete, circumscribed mass.  
* **Histological Features:** A mass-forming proliferation of melanocytes (benign or malignant).  
* **Characteristic Molecular Features (Supportive):** $GNAQ$ or $GNA11$ mutations are common (similar to uveal melanoma). $PLCB4$ and $CYSLTR2$ also seen.1  
* **Source Reference(s):** 1

### **2.9 Hematolymphoid Tumors**

This section includes only lymphomas and histiocytic tumors that are relatively common in the CNS or have special features when occurring there. The full classification is in the corresponding Hematopoietic Blue Book.1

##### **Primary diffuse large B-cell lymphoma of the CNS (PCNSL)**

* **Diagnosis (WHO CNS5):** Primary diffuse large B-cell lymphoma of the CNS  
* **Taxonomic Group:** Hematolymphoid tumors / Lymphomas / CNS lymphomas  
* **Previous Designation(s):** Same (WHO 2016).  
* **CNS WHO Grade:** N/A (malignant).  
* **Key Demographics & Location:** Typically older or immunocompromised patients.  
* **Histological Features:** Diffuse, perivascular "angiocentric" infiltrate of large, atypical lymphocytes.  
* **Source Reference(s):** 1

##### **Immunodeficiency-associated CNS lymphoma**

* **Diagnosis (WHO CNS5):** Immunodeficiency-associated CNS lymphoma  
* **Taxonomic Group:** Hematolymphoid tumors / Lymphomas / CNS lymphomas  
* **Previous Designation(s):** Same (WHO 2016).  
* **CNS WHO Grade:** N/A (malignant).  
* **Key Demographics & Location:** Patients with immunodeficiency (e.g., HIV/AIDS, post-transplant).  
* **Histological Features:** Often EBV-positive diffuse large B-cell lymphoma.  
* **Source Reference(s):** 1

*(This section also includes Lymphomatoid granulomatosis, Intravascular large B-cell lymphoma, MALT lymphoma of the dura, etc.)* 1

##### **Erdheim-Chester disease**

* **Diagnosis (WHO CNS5):** Erdheim-Chester disease  
* **Taxonomic Group:** Hematolymphoid tumors / Histiocytic tumors  
* **Previous Designation(s):** Same (WHO 2016).  
* **CNS WHO Grade:** N/A.  
* **Key Demographics & Location:** N/A from source.  
* **Histological Features:** Non-Langerhans cell histiocytosis. Infiltrate of foamy, lipid-laden histiocytes and Touton giant cells.  
* **Characteristic Molecular Features (Supportive):** $BRAF$ V600E mutation is common.  
* **Source Reference(s):** 1

##### **Rosai-Dorfman disease**

* **Diagnosis (WHO CNS5):** Rosai-Dorfman disease  
* **Taxonomic Group:** Hematolymphoid tumors / Histiocytic tumors  
* **Previous Designation(s):** Same (WHO 2016).  
* **CNS WHO Grade:** N/A.  
* **Key Demographics & Location:** N/A from source.  
* **Histological Features:** Non-Langerhans cell histiocytosis. Large histiocytes exhibiting "emperipolesis" (intact lymphocytes within the cytoplasm). S100 positive.  
* **Source Reference(s):** 1

##### **Langerhans cell histiocytosis**

* **Diagnosis (WHO CNS5):** Langerhans cell histiocytosis  
* **Taxonomic Group:** Hematolymphoid tumors / Histiocytic tumors  
* **Previous Designation(s):** Same (WHO 2016).  
* **CNS WHO Grade:** N/A.  
* **Key Demographics & Location:** Primarily children. Can affect bone (e.g., skull) or brain (e.g., hypothalamus).  
* **Histological Features:** Proliferation of Langerhans cells (histiocytes with grooved, "coffee-bean" nuclei). Positive for CD1a, Langerin, and S100.  
* **Characteristic Molecular Features (Supportive):** $BRAF$ V600E mutation is common.  
* **Source Reference(s):** 1

*(This section also includes Juvenile xanthogranuloma and Histiocytic sarcoma)* 1

### **2.10 Germ Cell Tumors**

These tumors typically arise in the midline, most often in the pineal or suprasellar regions.

##### **Mature teratoma**

* **Diagnosis (WHO CNS5):** Mature teratoma  
* **Taxonomic Group:** Germ cell tumors  
* **CNS WHO Grade:** N/A (benign).  
* **Histological Features:** Composed of fully differentiated, "mature" tissues from all three germ layers (e.g., skin, hair, teeth, cartilage, respiratory epithelium).  
* **Source Reference(s):** 1

##### **Immature teratoma**

* **Diagnosis (WHO CNS5):** Immature teratoma  
* **Taxonomic Group:** Germ cell tumors  
* **CNS WHO Grade:** N/A (malignant).  
* **Histological Features:** Composed of tissues from all three germ layers, but at least one component is "immature" (e.g., fetal tissue, primitive neuroepithelium).  
* **Source Reference(s):** 1

##### **Teratoma with somatic-type malignancy**

* **Diagnosis (WHO CNS5):** Teratoma with somatic-type malignancy  
* **Taxonomic Group:** Germ cell tumors  
* **CNS WHO Grade:** N/A (malignant).  
* **Histological Features:** A mature or immature teratoma in which one of the germ-cell components has transformed into a non-germ-cell cancer (e.g., a squamous cell carcinoma or a sarcoma arising within the teratoma).  
* **Source Reference(s):** 1

##### **Germinoma**

* **Diagnosis (WHO CNS5):** Germinoma  
* **Taxonomic Group:** Germ cell tumors  
* **CNS WHO Grade:** N/A (malignant, but highly radiosensitive).  
* **Histological Features:** Composed of large, primitive germ cells with prominent nucleoli, mixed with a reactive infiltrate of lymphocytes.  
* **Source Reference(s):** 1

##### **Embryonal carcinoma**

* **Diagnosis (WHO CNS5):** Embryonal carcinoma  
* **Taxonomic Group:** Germ cell tumors  
* **CNS WHO Grade:** N/A (malignant).  
* **Histological Features:** Malignant, primitive epithelial cells.  
* **Source Reference(s):** 1

##### **Yolk sac tumor**

* **Diagnosis (WHO CNS5):** Yolk sac tumor  
* **Taxonomic Group:** Germ cell tumors  
* **CNS WHO Grade:** N/A (malignant).  
* **Histological Features:** Malignant. Characteristic features include Schiller-Duval bodies (perivascular structures). Produces alpha-fetoprotein (AFP).  
* **Source Reference(s):** 1

##### **Choriocarcinoma**

* **Diagnosis (WHO CNS5):** Choriocarcinoma  
* **Taxonomic Group:** Germ cell tumors  
* **CNS WHO Grade:** N/A (malignant).  
* **Histological Features:** Malignant. Composed of syncytiotrophoblasts and cytotrophoblasts. Produces human chorionic gonadotropin (hCG).  
* **Source Reference(s):** 1

##### **Mixed germ cell tumor**

* **Diagnosis (WHO CNS5):** Mixed germ cell tumor  
* **Taxonomic Group:** Germ cell tumors  
* **CNS WHO Grade:** N/A (malignant).  
* **Histological Features:** Composed of two or more different germ cell tumor types (e.g., germinoma and teratoma).  
* **Source Reference(s):** 1

### **2.11 Tumors of the Sellar Region**

This family includes tumors arising in and around the sella turcica, including craniopharyngiomas and pituitary tumors.1

##### **Adamantinomatous craniopharyngioma**

* **Diagnosis (WHO CNS5):** Adamantinomatous craniopharyngioma  
* **Taxonomic Group:** Tumors of the sellar region  
* **Previous Designation(s):** Craniopharyngioma, adamantinomatous subtype (WHO 2016). This is now considered a distinct *type*, not a subtype.1  
* **CNS WHO Grade:** 1\.  
* **Key Demographics & Location:** Primarily children. Suprasellar location.  
* **Histological Features:** Nests of squamous epithelium in a loose "stellate reticulum." "Wet keratin" (ghost cells) and dystrophic calcification are characteristic.  
* **Essential Molecular Features (Definitional):** $CTNNB1$ (beta-catenin) mutation.1  
* **Source Reference(s):** 1

##### **Papillary craniopharyngioma**

* **Diagnosis (WHO CNS5):** Papillary craniopharyngioma  
* **Taxonomic Group:** Tumors of the sellar region  
* **Previous Designation(s):** Craniopharyngioma, papillary subtype (WHO 2016). This is now considered a distinct *type*, not a subtype.1  
* **CNS WHO Grade:** 1\.  
* **Key Demographics & Location:** Almost exclusively adults. Suprasellar location.  
* **Histological Features:** Composed of well-differentiated, non-keratinizing squamous epithelium forming papillary structures. Lacks "wet keratin" and calcification.  
* **Essential Molecular Features (Definitional):** $BRAF$ V600E mutation.1  
* **Source Reference(s):** 1

##### **Pituicytoma, granular cell tumor of the sellar region, and spindle cell oncocytoma**

* **Diagnosis (WHO CNS5):** Pituicytoma, granular cell tumor of the sellar region, and spindle cell oncocytoma  
* **Taxonomic Group:** Tumors of the sellar region  
* **Previous Designation(s):** These were three separate entities in WHO 2016\. They are now grouped into one section as a related group of tumors, though they are still classified separately.1  
* **CNS WHO Grade:** N/A from source (variable).  
* **Key Demographics & Location:** Adults. Sellar/suprasellar.  
* **Histological Features:**  
  * **Pituicytoma:** Bipolar spindle cells.  
  * **Granular cell tumor:** Large cells with abundant, eosinophilic, granular cytoplasm.  
  * **Spindle cell oncocytoma:** Spindle cells with oncGytic (eosinophilic, mitochondria-rich) cytoplasm.  
* **Source Reference(s):** 1

##### **Pituitary adenoma/PitNET**

* **Diagnosis (WHO CNS5):** Pituitary adenoma/PitNET  
* **Taxonomic Group:** Tumors of the sellar region  
* **Previous Designation(s):** Pituitary adenoma (WHO 2016).  
* **CNS WHO Grade:** N/A.  
* **Key Demographics & Location:** Adults. Sellar (arising from the anterior pituitary).  
* **Histological Features:** Benign neoplasm of adenohypophyseal cells. Classification is based on hormone and transcription factor expression (e.g., T-Pit, POU1F1, SF-1).1  
* **Essential Molecular Features (Definitional):** The term "PitNET" (Pituitary Neuroendocrine Tumor) has been added to the name to align with other neuroendocrine classifications.1  
* **Source Reference(s):** 1

##### **Pituitary blastoma**

* **Diagnosis (WHO CNS5):** Pituitary blastoma  
* **Taxonomic Group:** Tumors of the sellar region  
* **Previous Designation(s):** Newly recognized type.1  
* **CNS WHO Grade:** 4\.  
* **Key Demographics & Location:** Very young children (infants). Sellar region.  
* **Histological Features:** Malignant, triphasic embryonal neoplasm composed of (1) primitive blastemal cells, (2) neuroendocrine cells, and (3) Rathke epithelium.1  
* **Essential Molecular Features (Definitional):** Linked to germline or somatic $DICER1$ mutations.1  
* **Source Reference(s):** 1

### **2.12 Metastases to the CNS**

This section is for tumors that have spread to the CNS from a primary site elsewhere in the body.1

##### **Metastases to the brain and spinal cord parenchyma**

* **Diagnosis (WHO CNS5):** Metastases to the brain and spinal cord parenchyma  
* **Taxonomic Group:** Metastases to the CNS  
* **CNS WHO Grade:** N/A.  
* **Histological Features:** Varies by primary tumor (e.g., lung adenocarcinoma, breast carcinoma, melanoma).  
* **Essential Molecular Features (Definitional):** Diagnosis requires IHC and molecular markers to identify the primary source and guide targeted therapy (e.g., $EGFR$, $ALK$, $BRAF$, $HER2$, $PD-L1$).1  
* **Source Reference(s):** 1

##### **Metastases to the meninges**

* **Diagnosis (WHO CNS5):** Metastases to the meninges  
* **Taxonomic Group:** Metastases to the CNS  
* **CNS WHO Grade:** N/A.  
* **Histological Features:** Diffuse or nodular infiltration of the leptomeninges by metastatic cells (carcinomatosis, sarcomatosis, or melanomatosis).  
* **Source Reference(s):** 1

## **Section 3: Appendices (Source Data Tables)**

For agent validation and quick reference, the key summary tables from the source publication 1 are provided here.

### **Appendix A: The 2021 WHO Classification of Tumors of the Central Nervous System**

1

**Gliomas, glioneuronal tumors, and neuronal tumors**

* **Adult-type diffuse gliomas**  
  * Astrocytoma, IDH-mutant  
  * Oligodendroglioma, IDH-mutant, and 1p/19q-codeleted  
  * Glioblastoma, IDH-wildtype  
* **Pediatric-type diffuse low-grade gliomas**  
  * Diffuse astrocytoma, MYB- or MYBL1-altered  
  * Angiocentric glioma  
  * Polymorphous low-grade neuroepithelial tumor of the young  
  * Diffuse low-grade glioma, MAPK pathway-altered  
* **Pediatric-type diffuse high-grade gliomas**  
  * Diffuse midline glioma, H3 K27-altered  
  * Diffuse hemispheric glioma, H3 G34-mutant  
  * Diffuse pediatric-type high-grade glioma, H3-wildtype and IDH-wildtype  
  * Infant-type hemispheric glioma  
* **Circumscribed astrocytic gliomas**  
  * Pilocytic astrocytoma  
  * High-grade astrocytoma with piloid features  
  * Pleomorphic xanthoastrocytoma  
  * Subependymal giant cell astrocytoma  
  * Chordoid glioma  
  * Astroblastoma, MN1-altered  
* **Glioneuronal and neuronal tumors**  
  * Ganglioglioma  
  * Desmoplastic infantile ganglioglioma/desmoplastic infantile astrocytoma  
  * Dysembryoplastic neuroepithelial tumor  
  * Diffuse glioneuronal tumor with oligodendroglioma-like features and nuclear clusters  
  * Papillary glioneuronal tumor  
  * Rosette-forming glioneuronal tumor  
  * Myxoid glioneuronal tumor  
  * ...[source](https://www.cureus.com/articles/110804-larotrectinib-in-ntrk-fusion-positive-high-grade-glioneuronal-tumor-a-case-report)  
  * Cerebellar liponeurocytoma  
* **Ependymal tumors**  
  * Supratentorial ependymoma  
  * Supratentorial ependymoma, ZFTA fusion-positive  
  * Supratentorial ependymoma, YAP1 fusion-positive  
  * Posterior fossa ependymoma  
  * Posterior fossa ependymoma, group PFA  
  * Posterior fossa ependymoma, group PFB  
  * Spinal ependymoma  
  * Spinal ependymoma, MYCN-amplified  
  * Myxopapillary ependymoma  
  * Subependymoma

**Choroid plexus tumors**

* Choroid plexus papilloma  
* Atypical choroid plexus papilloma  
* Choroid plexus carcinoma

**Embryonal tumors**

* **Medulloblastoma**  
  * Medulloblastomas, molecularly defined  
    * Medulloblastoma, WNT-activated  
    * Medulloblastoma, SHH-activated and TP53-wildtype  
    * Medulloblastoma, SHH-activated and TP53-mutant  
    * Medulloblastoma, non-WNT/non-SHH  
  * Medulloblastomas, histologically defined  
* **Other CNS embryonal tumors**  
  * Atypical teratoid/rhabdoid tumor  
  * Cribriform neuroepithelial tumor  
  * Embryonal tumor with multilayered rosettes  
  * CNS neuroblastoma, FOXR2-activated  
  * CNS tumor with BCOR internal tandem duplication  
  * CNS embryonal tumor

**Pineal tumors**

* Pineocytoma  
* Pineal parenchymal tumor of intermediate differentiation  
* Pineoblastoma  
* Papillary tumor of the pineal region  
* Desmoplastic myxoid tumor of the pineal region, SMARCB1-mutant

**Cranial and paraspinal nerve tumors**

* Schwannoma  
* Neurofibroma  
* Perineurioma  
* Hybrid nerve sheath tumor  
* Malignant melanotic nerve sheath tumor  
* Malignant peripheral nerve sheath tumor  
* Paraganglioma

**Meningiomas**

* Meningioma

**Mesenchymal, non-meningothelial tumors**

* **Soft tissue tumors**  
  * Fibroblastic and myofibroblastic tumors  
    * Solitary fibrous tumor  
  * Vascular tumors  
    * Hemangiomas and vascular malformations  
    * Hemangioblastoma  
  * Skeletal muscle tumors  
    * Rhabdomyosarcoma  
  * Uncertain differentiation  
    * Intracranial mesenchymal tumor, FET-CREB fusion-positive  
    * CIC-rearranged sarcoma  
    * Primary intracranial sarcoma, DICER1-mutant  
    * Ewing sarcoma  
* **Chondro-osseous tumors**  
  * Chondrogenic tumors  
    * Mesenchymal chondrosarcoma  
    * Chondrosarcoma  
  * Notochordal tumors  
    * Chordoma (including poorly differentiated chordoma)

**Melanocytic tumors**

* Diffuse meningeal melanocytic neoplasms  
  * Meningeal melanocytosis and meningeal melanomatosis  
* Circumscribed meningeal melanocytic neoplasms  
  * Meningeal melanocytoma and meningeal melanoma

**Hematolymphoid tumors**

* **Lymphomas**  
  * CNS lymphomas  
    * Primary diffuse large B-cell lymphoma of the CNS  
    * Immunodeficiency-associated CNS lymphoma  
    * Lymphomatoid granulomatosis  
    * Intravascular large B-cell lymphoma  
  * Miscellaneous rare lymphomas in the CNS  
    * MALT lymphoma of the dura  
    * Other low-grade B-cell lymphomas of the CNS  
    * Anaplastic large cell lymphoma (ALK+/ALK-)  
    * T-cell and NK/T-cell lymphomas  
* **Histiocytic tumors**  
  * Erdheim-Chester disease  
  * Rosai-Dorfman disease  
  * Juvenile xanthogranuloma  
  * Langerhans cell histiocytosis  
  * Histiocytic sarcoma

**Germ cell tumors**

* Mature teratoma  
* Immature teratoma  
* Teratoma with somatic-type malignancy  
* Germinoma  
* Embryonal carcinoma  
* Yolk sac tumor  
* Choriocarcinoma  
* Mixed germ cell tumor

**Tumors of the sellar region**

* Adamantinomatous craniopharyngioma  
* Papillary craniopharyngioma  
* Pituicytoma, granular cell tumor of the sellar region, and spindle cell oncocytoma  
* Pituitary adenoma/PitNET  
* Pituitary blastoma

**Metastases to the CNS**

* Metastases to the brain and spinal cord parenchyma  
* Metastases to the meninges

### **Appendix B: Key Diagnostic Genes, Molecules, Pathways, and/or Combinations**

1

| Tumor Type | Genes/Molecular Profiles Characteristically Altered |
| :---- | :---- |
| Astrocytoma, IDH-mutant | $IDH1$, $IDH2$, $ATRX$, $TP53$, $CDKN2A/B$ |
| Oligodendroglioma, IDH-mutant, and 1p/19q-codeleted | $IDH1$, $IDH2$, 1p/19q, $TERT$ promoter, $CIC$, $FUBP1$, $NOTCH1$ |
| Glioblastoma, IDH-wildtype | IDH-wildtype, $TERT$ promoter, chromosomes 7/10, $EGFR$ |
| Diffuse astrocytoma, MYB- or MYBL1-altered | $MYB$, $MYBL1$ |
| Angiocentric glioma | $MYB$ |
| Polymorphous low-grade neuroepithelial tumor of the young | $BRAF$, $FGFR$ family |
| Diffuse low-grade glioma, MAPK pathway-altered | $FGFR1$, $BRAF$ |
| Diffuse midline glioma, H3 K27-altered | H3 K27, $TP53$, $ACVR1$, $PDGFRA$, $EGFR$, $EZHIP$ |
| Diffuse hemispheric glioma, H3 G34-mutant | H3 G34, $TP53$, $ATRX$ |
| Diffuse pediatric-type high-grade glioma, H3-wildtype, and IDH-wildtype | IDH-wildtype, H3-wildtype, $PDGFRA$, $MYCN$, $EGFR$ (methylome) |
| Infant-type hemispheric glioma | $NTRK$ family, $ALK$, $ROS1$, $MET$ |
| Pilocytic astrocytoma | $KIAA1549-BRAF$, $BRAF$, $NF1$ |
| High-grade astrocytoma with piloid features | $BRAF$, $NF1$, $ATRX$, $CDKN2A/B$ (methylome) |
| Pleomorphic xanthoastrocytoma | $BRAF$, $CDKN2A/B$ |
| Subependymal giant cell astrocytoma | $TSC1$, $TSC2$ |
| Chordoid glioma | $PRKCA$ |
| Astroblastoma, MN1-altered | $MN1$ |
| Ganglion cell tumors | $BRAF$ |
| Dysembryoplastic neuroepithelial tumor | $FGFR1$ |
| Diffuse glioneuronal tumor with oligodendroglioma-like features and nuclear clusters | Chromosome 14, (methylome) |
| Papillary glioneuronal tumor | $PRKCA$ |
| Rosette-forming glioneuronal tumor | $FGFR1$, $PIK3CA$, $NF1$ |
| Myxoid glioneuronal tumor | $PDGFRA$ |
| Diffuse leptomeningeal glioneuronal tumor | $KIAA1549-BRAF$ fusion, 1p (methylome) |
| Multinodular and vacuolating...[source](https://www.scribd.com/document/522715852/The-2021-WHO-Classification-of-Tumors) |  |
| Adamantinomatous craniopharyngioma | $CTNNB1$ |
| Papillary craniopharyngioma | $BRAF$ |

### **Appendix C: CNS WHO Grades of Selected Types**

1

| CNS WHO Grades of Selected Types |  |
| :---- | :---- |
| Astrocytoma, IDH-mutant | 2, 3, 4 |
| Oligodendroglioma, IDH-mutant, and 1p/19q-codeleted | 2, 3 |
| Glioblastoma, IDH-wildtype | 4 |
| Diffuse astrocytoma, MYB- or MYBL1-altered | 1 |
| Polymorphous low-grade neuroepithelial tumor of the young | 1 |
| Diffuse hemispheric glioma, H3 G34-mutant | 4 |
| Pleomorphic xanthoastrocytoma | 2, 3 |
| Multinodular and vacuolating neuronal tumor | 1 |
| Supratentorial ependymoma | 2, 3 |
| Posterior fossa ependymoma | 2, 3 |
| Myxopapillary ependymoma | 2 |
| Meningioma | 1, 2, 3 |
| Solitary fibrous tumor | 1, 2, 3 |

### **Appendix D: Newly Recognized Tumor Types in WHO CNS5**

1

* Diffuse astrocytoma, MYB- or MYBL1-altered  
* Polymorphous low-grade neuroepithelial tumor of the young  
* Diffuse low-grade glioma, MAPK pathway-altered  
* Diffuse hemispheric glioma, H3 G34-mutant  
* Diffuse pediatric-type high-grade glioma, H3-wildtype and IDH-wildtype  
* Infant-type hemispheric glioma  
* High-grade astrocytoma with piloid features  
* Diffuse glioneuronal tumor with oligodendroglioma-like features and nuclear clusters (provisional type)  
* Myxoid glioneuronal tumor  
* Multinodular and vacuolating neuronal tumor  
* Supratentorial ependymoma, YAP1 fusion-positive  
* Posterior fossa ependymoma, group PFA  
* Posterior fossa ependymoma, group PFB  
* Spinal ependymoma, MYCN-amplified  
* Cribriform neuroepithelial tumor (provisional type)  
* CNS neuroblastoma, FOXR2-activated  
* CNS tumor with BCOR internal tandem duplication  
* Desmoplastic myxoid tumor of the pineal region, SMARCB1-mutant  
* Intracranial mesenchymal tumor, FET-CREB fusion-positive (provisional type)  
* CIC-rearranged sarcoma  
* Primary intracranial sarcoma, DICER1-mutant  
* Pituitary blastoma

### **Appendix E: Tumor Types With Revised Nomenclature or Revised Placement**

1

* Astrocytoma, IDH-mutant (covers grades 2-4; eliminates the term "Glioblastoma, IDH-mutant")  
* Diffuse midline glioma, H3 K27-altered (changes "mutant" to "altered" given multiple mechanisms)  
* Chordoid glioma (removes site designation)  
* Astroblastoma, MN1-altered (adds genetic modifier)  
* Supratentorial ependymoma, ZFTA fusion-positive (reflects changes in fusion partner and gene nomenclature)  
* Embryonal tumor with multilayered rosettes (removes genetic modifier to allow for genetic subtypes)  
* Malignant melanotic nerve sheath tumor (conforms to terminology in soft tissue pathology literature)  
* Solitary fibrous tumor (removes the term "hemangiopericytoma" to conform fully with soft tissue pathology nomenclature)  
* Mesenchymal chondrosarcoma (formerly a subtype)  
* Adamantinomatous craniopharyngioma (formerly a subtype)  
* Papillary craniopharyngioma (formerly a subtype)  
* Pituicytoma, granular cell tumor of the sellar region, and spindle cell oncocytoma (grouped rather than separate)  
* Pituitary adenoma/PitNET (adds the term "PitNET")

#### **Works cited**

1. WHO\_2021s.pdf