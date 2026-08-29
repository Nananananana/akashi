"""Chinese source material.

Chinese has no spaces, so every case here is a test of whether the segmenter
produces sentences or produces a paragraph. It is also where the measure-word
quantities live -- ``3 小时``, ``12 个`` -- and where a bare numeral is a word
as often as a count, which is the trade the extractor makes and this is where
its price gets measured.
"""

from __future__ import annotations

from ..case import PlantKind as K
from ..generation import Document, GenreSpec
from ..generation import SentenceSpec as S

__all__ = ["CHINESE"]

_CONTRACT = GenreSpec(
    language="zh",
    genre="contract",
    question="通知期限和赔偿上限是多少?",
    documents=(
        Document(
            document_id="doc_msa_zh",
            source_path="contracts/2025-服务协议.md",
            section="条款",
            paragraphs=(
                "本文件为双方服务协议的摘要，签署日期与签署方另见附表。",
                "根据{{F:notice_clause}}第30条{{/F}}，任何一方均可提前"
                "{{F:notice_days}}30天{{/F}}书面通知解除本协议。",
                "{{F:cap_clause}}第12条{{/F}}规定的赔偿责任上限为{{F:cap_amount}}1,200万元{{/F}}。",
                "付款期限为收到发票后{{F:pay_days}}45天{{/F}}内，"
                "逾期利率为年{{F:interest}}3.5%{{/F}}。",
                "适用法律与管辖法院由双方另行协商确定。",
            ),
        ),
        Document(
            document_id="doc_amend_zh",
            source_path="contracts/2026-补充协议.md",
            section="补充",
            paragraphs=(
                "本补充协议对上述条款作出变更。",
                "合同期限为{{F:term_years}}3年{{/F}}，"
                "除非提前{{F:renew_days}}60天{{/F}}提出异议，否则自动续约。",
                "变更自{{F:effective}}2026年4月1日{{/F}}起生效。",
            ),
        ),
    ),
    sentences=(
        S(
            K.GROUNDED,
            "根据第30条，任何一方均可提前30天书面通知解除协议。",
            "第30条",
            "notice_clause",
        ),
        S(K.GROUNDED, "赔偿责任上限为1,200万元。", "1,200万元", "cap_amount"),
        S(K.GROUNDED, "付款期限为收到发票后45天内。", "45天", "pay_days"),
        S(K.GROUNDED, "合同期限为3年，并可自动续约。", "3年", "term_years"),
        S(K.DIGIT_DRIFT, "根据第13条，任何一方均可解除协议。", "第13条", "notice_clause"),
        S(K.DIGIT_DRIFT, "赔偿责任上限为1,300万元。", "1,300万元", "cap_amount"),
        S(K.DIGIT_DRIFT, "变更自2026年4月10日起生效。", "2026年4月10日", "effective"),
        S(K.UNIT_SWAP, "赔偿责任上限为1,200亿元。", "1,200亿元", "cap_amount"),
        S(K.UNIT_SWAP, "通知期限为提前30个月。", "30个月", "notice_days"),
        S(K.INVENTED_PARTICULAR, "违约金为250万元。", "250万元"),
        S(K.INVENTED_PARTICULAR, "续约事项见第41条的规定。", "第41条"),
        S(K.DERIVED_VALUE, "通知与续约期限合计为90天。", "90天"),
        S(K.ENTITY_SWAP, "赔偿责任上限见第30条。", "第30条", "notice_clause"),
        S(K.ENTITY_SWAP, "付款期限为收到发票后60天内。", "60天", "renew_days"),
        S(K.CROSS_DOCUMENT_STITCH, "第12条规定合同期限为3年。", expect_verdict="grounded"),
        S(K.NEGATION_FLIP, "第30条不允许以书面通知解除协议。", expect_verdict="grounded"),
        S(K.NEGATION_FLIP, "本协议未设赔偿责任上限。", expect_verdict="unbearing"),
        S(K.FAITHFUL_PARAPHRASE, "简言之，任何一方都可以终止这项安排。"),
        S(K.FAITHFUL_PARAPHRASE, "值得注意的是，赔偿的范围是有边界的。"),
    ),
)

_CLINICAL = GenreSpec(
    language="zh",
    genre="clinical",
    question="用药剂量和复诊间隔是多少?",
    documents=(
        Document(
            document_id="doc_chart_zh",
            source_path="clinical/2026-08-病历.md",
            section="经过",
            paragraphs=(
                "门诊随访记录。既往史与家族史另有记载，此处不再重复。",
                "口服{{F:dose}}5mg{{/F}}，每日{{F:times}}2次{{/F}}，连续{{F:days}}14天{{/F}}。",
                "体重{{F:weight}}62.4公斤{{/F}}，血压{{F:bp}}128/82{{/F}}。",
                "{{F:interval}}4周{{/F}}后复诊，{{F:blood}}2周{{/F}}后复查血常规。",
                "已给予饮食指导，相关资料由营养科提供。",
            ),
        ),
        Document(
            document_id="doc_lab_zh",
            source_path="clinical/2026-08-检验.md",
            section="检验",
            paragraphs=(
                "检验科报告如下。",
                "糖化血红蛋白为{{F:hba1c}}7.2%{{/F}}，eGFR为{{F:egfr}}68{{/F}}。",
            ),
        ),
    ),
    sentences=(
        S(K.GROUNDED, "口服5mg，每日2次，连续14天。", "5mg", "dose"),
        S(K.GROUNDED, "4周后复诊。", "4周", "interval"),
        S(K.GROUNDED, "体重记录为62.4公斤。", "62.4公斤", "weight"),
        S(K.GROUNDED, "糖化血红蛋白为7.2%。", "7.2%", "hba1c"),
        S(K.DIGIT_DRIFT, "口服50mg，每日2次。", "50mg", "dose"),
        S(K.DIGIT_DRIFT, "体重记录为62.8公斤。", "62.8公斤", "weight"),
        S(K.DIGIT_DRIFT, "糖化血红蛋白为7.9%。", "7.9%", "hba1c"),
        S(K.UNIT_SWAP, "口服5克，每日2次。", "5克", "dose"),
        S(K.UNIT_SWAP, "4天后复诊。", "4天", "interval"),
        S(K.INVENTED_PARTICULAR, "血药浓度报告为12.6。", "12.6"),
        S(K.INVENTED_PARTICULAR, "另给予250mg静脉滴注。", "250mg"),
        S(K.DERIVED_VALUE, "14天共计服药28次。", "28次"),
        S(K.ENTITY_SWAP, "2周后复诊。", "2周", "blood"),
        S(K.ENTITY_SWAP, "每日2次，连续4周。", "4周", "interval"),
        S(K.CROSS_DOCUMENT_STITCH, "eGFR为68，体重为62.4公斤。", expect_verdict="grounded"),
        S(K.NEGATION_FLIP, "并非口服5mg每日2次。", expect_verdict="grounded"),
        S(K.NEGATION_FLIP, "未安排复诊。", expect_verdict="unbearing"),
        S(K.FAITHFUL_PARAPHRASE, "目前的方案是继续服药。"),
        S(K.FAITHFUL_PARAPHRASE, "检验结果仍需持续观察。"),
    ),
)

_SPEC = GenreSpec(
    language="zh",
    genre="engineering",
    question="公差和质量要求是多少?",
    documents=(
        Document(
            document_id="doc_spec_zh",
            source_path="specs/2026-外壳规格.md",
            section="要求",
            paragraphs=(
                "本规格书规定外壳的技术要求，修订记录附于文末。",
                "外形尺寸公差为{{F:tolerance}}0.02毫米{{/F}}，质量不超过{{F:mass}}2.4公斤{{/F}}。",
                "工作温度范围为{{F:temp}}-20度{{/F}}至{{F:temp_max}}60度{{/F}}。",
                "适用标准为{{F:standard}}ISO 9001{{/F}}，布局见{{F:drawing}}第4图{{/F}}。",
                "装配与检验流程详见配套手册。",
            ),
        ),
        Document(
            document_id="doc_rev_zh",
            source_path="specs/2026-修订通知.md",
            section="修订",
            paragraphs=(
                "本通知记录对上述规格的修订。",
                "版本为{{F:version}}1.2.3{{/F}}，自{{F:from}}2026年8月30日{{/F}}起适用。",
            ),
        ),
    ),
    sentences=(
        S(K.GROUNDED, "外形尺寸公差为0.02毫米。", "0.02毫米", "tolerance"),
        S(K.GROUNDED, "质量不超过2.4公斤。", "2.4公斤", "mass"),
        S(K.GROUNDED, "适用标准为ISO 9001。", "ISO 9001", "standard"),
        S(K.GROUNDED, "版本1.2.3自2026年8月30日起适用。", "1.2.3", "version"),
        S(K.DIGIT_DRIFT, "外形尺寸公差为0.2毫米。", "0.2毫米", "tolerance"),
        S(K.DIGIT_DRIFT, "质量不超过2.6公斤。", "2.6公斤", "mass"),
        S(K.DIGIT_DRIFT, "自2026年8月13日起适用。", "2026年8月13日", "from"),
        S(K.UNIT_SWAP, "质量不超过2.4克。", "2.4克", "mass"),
        S(K.UNIT_SWAP, "公差为0.02米。", "0.02米", "tolerance"),
        S(K.INVENTED_PARTICULAR, "耐压为350千帕。", "350千帕"),
        S(K.INVENTED_PARTICULAR, "ISO 14001同样适用。", "ISO 14001"),
        S(K.DERIVED_VALUE, "工作温度跨度为80度。", "80度"),
        S(K.ENTITY_SWAP, "布局见第9图。", "第9图"),
        S(K.ENTITY_SWAP, "质量上限为1.2公斤。", "1.2公斤"),
        S(K.CROSS_DOCUMENT_STITCH, "版本1.2.3将公差改为0.02毫米。", expect_verdict="grounded"),
        S(K.NEGATION_FLIP, "质量并未限定为2.4公斤。", expect_verdict="grounded"),
        S(K.NEGATION_FLIP, "未规定尺寸公差。", expect_verdict="unbearing"),
        S(K.FAITHFUL_PARAPHRASE, "尺寸方面的要求相当严格。"),
        S(K.FAITHFUL_PARAPHRASE, "重量上限对设计构成了实际的约束。"),
    ),
)

_PROTECTED = GenreSpec(
    language="zh",
    genre="protected",
    question="负责人和期限是?",
    documents=(
        Document(
            document_id="doc_case_zh",
            source_path="cases/2026-08-分工表.md",
            section="分工",
            paragraphs=(
                "各项事务的负责人与期限如下。",
                "负责人为<PERSON_001>，期限为{{F:deadline}}2026年8月30日{{/F}}。",
            ),
        ),
    ),
    sentences=(
        S(K.PLACEHOLDER_RESIDUE, "负责人为<PERSON_001>，期限为2026年8月30日。", "<PERSON_001>"),
        S(K.PLACEHOLDER_RESIDUE, "<PERSON_001>将接手本事项。", "<PERSON_001>"),
    ),
    protected=True,
    tier=(),
)

CHINESE: tuple[GenreSpec, ...] = (_CONTRACT, _CLINICAL, _SPEC, _PROTECTED)
