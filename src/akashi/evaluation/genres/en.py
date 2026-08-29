"""English source material.

The abbreviation list earns its keep here. ``Sec. 4``, ``Art. 12``, ``Fig. 2``
and ``approx.`` all sit next to a number, which is exactly where a wrong
sentence boundary would split a particular away from the thing that gives it
meaning -- so the genres put them next to plants on purpose.
"""

from __future__ import annotations

from ..case import PlantKind as K
from ..generation import Document, GenreSpec
from ..generation import SentenceSpec as S

__all__ = ["ENGLISH"]

_CONTRACT = GenreSpec(
    language="en",
    genre="contract",
    question="what is the notice period and the cap on liability?",
    documents=(
        Document(
            document_id="doc_msa_en",
            source_path="contracts/2025-msa.md",
            section="Terms",
            paragraphs=(
                "This summarises the master services agreement between the parties. "
                "The execution date and the signatories are listed in the schedule.",
                "Under {{F:notice_clause}}Section 4(b){{/F}}, either party may "
                "terminate on {{F:notice_days}}30 days{{/F}} written notice.",
                "Liability under {{F:cap_clause}}Art. 12{{/F}} is capped at "
                "{{F:cap_amount}}45,000 dollars{{/F}} in aggregate.",
                "Invoices fall due within {{F:pay_days}}45 days{{/F}} of receipt, "
                "and interest accrues at {{F:interest}}3.5%{{/F}} per annum.",
                "Governing law and jurisdiction are to be agreed separately.",
            ),
        ),
        Document(
            document_id="doc_amend_en",
            source_path="contracts/2026-amendment.md",
            section="Amendment",
            paragraphs=(
                "This amendment varies the agreement above.",
                "The term is {{F:term_years}}3 years{{/F}}, renewing automatically "
                "unless notice is given {{F:renew_days}}60 days{{/F}} in advance.",
                "The amendment takes effect on {{F:effective}}April 1, 2026{{/F}}.",
            ),
        ),
    ),
    sentences=(
        S(
            K.GROUNDED,
            "Under Section 4(b), either party may terminate on 30 days notice.",
            "Section 4(b)",
            "notice_clause",
        ),
        S(
            K.GROUNDED,
            "Liability is capped at 45,000 dollars in aggregate.",
            "45,000 dollars",
            "cap_amount",
        ),
        S(K.GROUNDED, "Invoices fall due within 45 days of receipt.", "45 days", "pay_days"),
        S(K.GROUNDED, "The term is 3 years and renews automatically.", "3 years", "term_years"),
        S(
            K.DIGIT_DRIFT,
            "Under Section 4(d), either party may terminate.",
            "Section 4(d)",
            "notice_clause",
        ),
        S(
            K.DIGIT_DRIFT,
            "Liability is capped at 54,000 dollars in aggregate.",
            "54,000 dollars",
            "cap_amount",
        ),
        S(
            K.DIGIT_DRIFT,
            "The amendment takes effect on April 11, 2026.",
            "April 11, 2026",
            "effective",
        ),
        S(
            K.UNIT_SWAP,
            "Interest accrues at 3.5 percentage points per annum.",
            "3.5 percentage points",
            "interest",
        ),
        S(
            K.UNIT_SWAP,
            "Either party may terminate on 30 months written notice.",
            "30 months",
            "notice_days",
        ),
        S(K.INVENTED_PARTICULAR, "A break fee of 12,500 dollars applies.", "12,500 dollars"),
        S(K.INVENTED_PARTICULAR, "Renewal is governed by Art. 41 of the agreement.", "Art. 41"),
        S(K.DERIVED_VALUE, "Notice and renewal together come to 90 days.", "90 days"),
        S(
            K.ENTITY_SWAP,
            "The cap on liability is set out in Section 4(b).",
            "Section 4(b)",
            "notice_clause",
        ),
        S(K.ENTITY_SWAP, "Invoices fall due within 60 days of receipt.", "60 days", "renew_days"),
        S(
            K.CROSS_DOCUMENT_STITCH,
            "Art. 12 provides that the term is 3 years.",
            expect_verdict="grounded",
        ),
        S(
            K.NEGATION_FLIP,
            "Section 4(b) does not permit termination on written notice.",
            expect_verdict="grounded",
        ),
        S(
            K.NEGATION_FLIP,
            "Liability under this agreement is not capped.",
            expect_verdict="unbearing",
        ),
        S(K.FAITHFUL_PARAPHRASE, "In short, either side can bring the arrangement to an end."),
        S(
            K.FAITHFUL_PARAPHRASE,
            "It is worth noting that the exposure is bounded rather than open.",
        ),
    ),
)

_CLINICAL = GenreSpec(
    language="en",
    genre="clinical",
    question="what is the dose and the follow-up interval?",
    documents=(
        Document(
            document_id="doc_chart_en",
            source_path="clinical/2026-08-notes.md",
            section="Progress",
            paragraphs=(
                "Outpatient progress note. History and family history are recorded "
                "separately and are not repeated here.",
                "The dose is {{F:dose}}5mg{{/F}} taken {{F:times}}twice daily{{/F}} "
                "for {{F:days}}14 days{{/F}}.",
                "Weight was {{F:weight}}62.4kg{{/F}} and blood pressure "
                "{{F:bp}}128/82{{/F}} at this visit.",
                "Review in {{F:interval}}4 weeks{{/F}}, with bloods drawn at "
                "{{F:blood}}2 weeks{{/F}}.",
                "Dietary advice was given and the leaflet was supplied.",
            ),
        ),
        Document(
            document_id="doc_lab_en",
            source_path="clinical/2026-08-labs.md",
            section="Results",
            paragraphs=(
                "Reported by the laboratory.",
                "HbA1c was {{F:hba1c}}7.2%{{/F}} and eGFR was {{F:egfr}}68{{/F}}.",
            ),
        ),
    ),
    sentences=(
        S(K.GROUNDED, "The dose is 5mg twice daily for 14 days.", "5mg", "dose"),
        S(K.GROUNDED, "Review is scheduled in 4 weeks.", "4 weeks", "interval"),
        S(K.GROUNDED, "Weight was recorded as 62.4kg.", "62.4kg", "weight"),
        S(K.GROUNDED, "HbA1c was 7.2% at the last draw.", "7.2%", "hba1c"),
        S(K.DIGIT_DRIFT, "The dose is 50mg twice daily.", "50mg", "dose"),
        S(K.DIGIT_DRIFT, "Weight was recorded as 62.8kg.", "62.8kg", "weight"),
        S(K.DIGIT_DRIFT, "HbA1c was 7.9% at the last draw.", "7.9%", "hba1c"),
        S(K.UNIT_SWAP, "The dose is 5 grams twice daily.", "5 grams", "dose"),
        S(K.UNIT_SWAP, "Review is scheduled in 4 days.", "4 days", "interval"),
        S(K.INVENTED_PARTICULAR, "Serum level was reported as 12.6 units.", "12.6 units"),
        S(K.INVENTED_PARTICULAR, "An additional 250mg was given by infusion.", "250mg"),
        S(K.DERIVED_VALUE, "Over 14 days that is 28 doses in total.", "28 doses"),
        S(K.ENTITY_SWAP, "Review is scheduled in 2 weeks.", "2 weeks", "blood"),
        S(K.ENTITY_SWAP, "The course runs twice daily for 4 weeks.", "4 weeks", "interval"),
        S(
            K.CROSS_DOCUMENT_STITCH,
            "eGFR was 68 and weight was 62.4kg at the same visit.",
            expect_verdict="grounded",
        ),
        S(K.NEGATION_FLIP, "The dose is not 5mg twice daily.", expect_verdict="grounded"),
        S(K.NEGATION_FLIP, "No follow-up was arranged.", expect_verdict="unbearing"),
        S(K.FAITHFUL_PARAPHRASE, "The medication is to be continued for the time being."),
        S(K.FAITHFUL_PARAPHRASE, "The results will need watching over the coming period."),
    ),
)

_SPEC = GenreSpec(
    language="en",
    genre="engineering",
    question="what are the tolerance and the mass requirement?",
    documents=(
        Document(
            document_id="doc_spec_en",
            source_path="specs/2026-enclosure.md",
            section="Requirements",
            paragraphs=(
                "This specification sets out the requirements for the enclosure. "
                "The revision history is appended at the end of the document.",
                "The dimensional tolerance is {{F:tolerance}}0.02mm{{/F}} and the "
                "mass shall not exceed {{F:mass}}2.4kg{{/F}}.",
                "The operating range is {{F:temp}}-20 degrees{{/F}} to "
                "{{F:temp_max}}60 degrees{{/F}}.",
                "The applicable standard is {{F:standard}}ISO 9001{{/F}}; see "
                "{{F:drawing}}Fig. 4{{/F}} for the layout and "
                "{{F:table}}Table 2{{/F}} for the dimensions.",
                "Assembly and inspection procedures are covered in the companion volume.",
            ),
        ),
        Document(
            document_id="doc_rev_en",
            source_path="specs/2026-revision.md",
            section="Revision",
            paragraphs=(
                "This notice records a revision to the specification above.",
                "The revision is {{F:version}}1.2.3{{/F}}, effective {{F:from}}2026-08-30{{/F}}.",
            ),
        ),
    ),
    sentences=(
        S(K.GROUNDED, "The dimensional tolerance is 0.02mm.", "0.02mm", "tolerance"),
        S(K.GROUNDED, "Mass shall not exceed 2.4kg.", "2.4kg", "mass"),
        S(K.GROUNDED, "The applicable standard is ISO 9001.", "ISO 9001", "standard"),
        S(K.GROUNDED, "Revision 1.2.3 is effective from 2026-08-30.", "1.2.3", "version"),
        S(K.DIGIT_DRIFT, "The dimensional tolerance is 0.2mm.", "0.2mm", "tolerance"),
        S(K.DIGIT_DRIFT, "Mass shall not exceed 2.6kg.", "2.6kg", "mass"),
        S(K.DIGIT_DRIFT, "The revision is effective from 2026-08-13.", "2026-08-13", "from"),
        S(K.UNIT_SWAP, "Mass shall not exceed 2.4 grams.", "2.4 grams", "mass"),
        S(K.UNIT_SWAP, "The tolerance is 0.02 metres.", "0.02 metres", "tolerance"),
        S(K.INVENTED_PARTICULAR, "The pressure rating is 350 kilopascals.", "350 kilopascals"),
        S(K.INVENTED_PARTICULAR, "ISO 14001 also applies to the enclosure.", "ISO 14001"),
        S(K.DERIVED_VALUE, "The operating range spans 80 degrees.", "80 degrees"),
        S(K.ENTITY_SWAP, "See Table 2 for the layout of the enclosure.", "Table 2", "table"),
        S(K.ENTITY_SWAP, "The lower operating limit is 60 degrees.", "60 degrees", "temp_max"),
        S(
            K.CROSS_DOCUMENT_STITCH,
            "Revision 1.2.3 changed the tolerance to 0.02mm.",
            expect_verdict="grounded",
        ),
        S(K.NEGATION_FLIP, "Mass is not limited to 2.4kg.", expect_verdict="grounded"),
        S(K.NEGATION_FLIP, "No dimensional tolerance is specified.", expect_verdict="unbearing"),
        S(K.FAITHFUL_PARAPHRASE, "The dimensional requirements are demanding by any measure."),
        S(K.FAITHFUL_PARAPHRASE, "A ceiling on weight is a real constraint on the design."),
    ),
)

_PROTECTED = GenreSpec(
    language="en",
    genre="protected",
    question="who is assigned and by when?",
    documents=(
        Document(
            document_id="doc_case_en",
            source_path="cases/2026-08-assignments.md",
            section="Assignments",
            paragraphs=(
                "Assignments and deadlines by matter.",
                "Assigned to <PERSON_001>, due {{F:deadline}}2026-08-30{{/F}}.",
            ),
        ),
    ),
    sentences=(
        S(K.PLACEHOLDER_RESIDUE, "It is assigned to <PERSON_001>, due 2026-08-30.", "<PERSON_001>"),
        S(K.PLACEHOLDER_RESIDUE, "<PERSON_001> will be taking this one over.", "<PERSON_001>"),
    ),
    protected=True,
)

ENGLISH: tuple[GenreSpec, ...] = (_CONTRACT, _CLINICAL, _SPEC, _PROTECTED)
