"""Japanese source material.

Three genres, and the plants are chosen for what goes wrong in each. A clause
number in a contract, a dose in a clinical note, a tolerance in a
specification: each is a particular whose neighbours read identically whether
it is right or wrong, which is the failure ADR-0004 exists for.

The kanji-numeral cases are here on purpose. ``第三十条`` and ``三千人`` are
extracted; ``三人`` is not, because a bare kanji numeral is a word as often as
a count -- and the corpus is where that trade stops being an assertion in a
docstring and becomes a number.
"""

from __future__ import annotations

from ..case import PlantKind as K
from ..generation import Document, GenreSpec
from ..generation import SentenceSpec as S

__all__ = ["JAPANESE"]

_CONTRACT = GenreSpec(
    language="ja",
    genre="contract",
    question="解約通知の期間と賠償の上限は?",
    documents=(
        Document(
            document_id="doc_msa_ja",
            source_path="contracts/2025-業務委託契約.md",
            section="契約条項",
            paragraphs=(
                "本書は甲乙間の業務委託契約の要約である。締結日および当事者は別表に記載する。",
                "{{F:notice_clause}}第30条{{/F}}により、いずれの当事者も"
                "{{F:notice_days}}30日{{/F}}前の書面通知をもって本契約を解約できる。",
                "{{F:cap_clause}}第12条{{/F}}に定める賠償責任の上限額は"
                "{{F:cap_amount}}1,200万円{{/F}}とする。",
                "支払期日は請求書受領後 {{F:pay_days}}45日{{/F}} 以内、"
                "遅延利率は年 {{F:interest}}3.5%{{/F}} とする。",
                "本契約の準拠法および管轄については別途協議のうえ定めるものとする。",
            ),
        ),
        Document(
            document_id="doc_amend_ja",
            source_path="contracts/2026-覚書.md",
            section="覚書",
            paragraphs=(
                "本覚書は上記契約の一部を変更するものである。",
                "契約期間を {{F:term_years}}3年{{/F}} とし、"
                "{{F:renew_days}}60日{{/F}} 前までに申し出がない限り自動更新する。",
                "変更の効力発生日は {{F:effective}}2026年4月1日{{/F}} とする。",
            ),
        ),
    ),
    sentences=(
        S(
            K.GROUNDED,
            "第30条により、いずれの当事者も30日前の書面通知で解約できます。",
            "第30条",
            "notice_clause",
        ),
        S(K.GROUNDED, "賠償責任の上限は1,200万円です。", "1,200万円", "cap_amount"),
        S(K.GROUNDED, "支払期日は請求書受領後45日以内です。", "45日", "pay_days"),
        S(K.GROUNDED, "契約期間は3年で、自動更新の条項があります。", "3年", "term_years"),
        S(K.DIGIT_DRIFT, "第13条により、いずれの当事者も解約できます。", "第13条", "notice_clause"),
        S(K.DIGIT_DRIFT, "賠償責任の上限は1,300万円です。", "1,300万円", "cap_amount"),
        S(K.DIGIT_DRIFT, "変更の効力発生日は2026年4月10日です。", "2026年4月10日", "effective"),
        S(K.UNIT_SWAP, "賠償責任の上限は1,200億円です。", "1,200億円", "cap_amount"),
        S(K.UNIT_SWAP, "解約通知の期間は30ヶ月前とされています。", "30ヶ月", "notice_days"),
        S(K.INVENTED_PARTICULAR, "違約金は 250万円 と定められています。", "250万円"),
        S(K.INVENTED_PARTICULAR, "更新の申し出は第41条に規定があります。", "第41条"),
        S(K.DERIVED_VALUE, "通知期間と更新期限を合わせると90日になります。", "90日"),
        S(K.ENTITY_SWAP, "賠償責任の上限は第30条に定められています。", "第30条", "notice_clause"),
        S(K.ENTITY_SWAP, "支払期日は請求書受領後60日以内です。", "60日", "renew_days"),
        S(
            K.CROSS_DOCUMENT_STITCH,
            "第12条により、契約期間は3年とされています。",
            expect_verdict="grounded",
        ),
        S(
            K.NEGATION_FLIP,
            "第30条による解約は書面通知では認められません。",
            expect_verdict="grounded",
        ),
        S(K.NEGATION_FLIP, "賠償責任に上限は設けられていません。", expect_verdict="unbearing"),
        S(K.FAITHFUL_PARAPHRASE, "要するに、どちらの側からでも契約を終わらせることができます。"),
        S(K.FAITHFUL_PARAPHRASE, "賠償の範囲には上限が設けられている点に留意が必要です。"),
    ),
)

_CLINICAL = GenreSpec(
    language="ja",
    genre="clinical",
    question="投与量と経過観察の間隔は?",
    documents=(
        Document(
            document_id="doc_chart_ja",
            source_path="clinical/2026-08-診療録.md",
            section="経過",
            paragraphs=(
                "外来における経過の記録である。既往歴および家族歴は別紙に記載する。",
                "内服は {{F:dose}}5mg{{/F}} を1日 {{F:times}}2回{{/F}}、"
                "{{F:days}}14日間{{/F}} 継続とした。",
                "体重は {{F:weight}}62.4kg{{/F}}、血圧は {{F:bp}}128/82{{/F}} であった。",
                "次回受診は {{F:interval}}4週間{{/F}} 後、"
                "採血は {{F:blood}}2週間{{/F}} 後に実施する。",
                "生活指導の詳細については栄養部からの資料を参照のこと。",
            ),
        ),
        Document(
            document_id="doc_lab_ja",
            source_path="clinical/2026-08-検査結果.md",
            section="検査",
            paragraphs=(
                "検査部からの報告である。",
                "HbA1c は {{F:hba1c}}7.2%{{/F}}、eGFR は {{F:egfr}}68{{/F}} であった。",
            ),
        ),
    ),
    sentences=(
        S(K.GROUNDED, "内服は5mgを1日2回、14日間継続とされています。", "5mg", "dose"),
        S(K.GROUNDED, "次回受診は4週間後の予定です。", "4週間", "interval"),
        S(K.GROUNDED, "体重は62.4kgと記録されています。", "62.4kg", "weight"),
        S(K.GROUNDED, "HbA1c は7.2%でした。", "7.2%", "hba1c"),
        S(K.DIGIT_DRIFT, "内服は50mgを1日2回とされています。", "50mg", "dose"),
        S(K.DIGIT_DRIFT, "体重は62.8kgと記録されています。", "62.8kg", "weight"),
        S(K.DIGIT_DRIFT, "HbA1c は7.9%でした。", "7.9%", "hba1c"),
        S(K.UNIT_SWAP, "内服は5gを1日2回とされています。", "5g", "dose"),
        S(K.UNIT_SWAP, "次回受診は4日間後の予定です。", "4日間", "interval"),
        S(K.INVENTED_PARTICULAR, "血中濃度は 12.6 と報告されています。", "12.6"),
        S(K.INVENTED_PARTICULAR, "追加で 250mg の点滴を行いました。", "250mg"),
        S(K.DERIVED_VALUE, "14日間で合計28回の内服となります。", "28回"),
        S(K.ENTITY_SWAP, "次回受診は2週間後の予定です。", "2週間", "blood"),
        S(K.ENTITY_SWAP, "内服は1日2回、4週間継続とされています。", "4週間", "interval"),
        S(
            K.CROSS_DOCUMENT_STITCH,
            "eGFR は68で、体重は62.4kgでした。",
            expect_verdict="grounded",
        ),
        S(K.NEGATION_FLIP, "内服は5mgを1日2回とはされていません。", expect_verdict="grounded"),
        S(K.NEGATION_FLIP, "経過観察の予定は組まれていません。", expect_verdict="unbearing"),
        S(K.FAITHFUL_PARAPHRASE, "服薬は当面のあいだ続ける方針とされています。"),
        S(K.FAITHFUL_PARAPHRASE, "検査値については引き続き経過を見る必要があります。"),
    ),
)

_SPEC = GenreSpec(
    language="ja",
    genre="engineering",
    question="公差と質量の要求は?",
    documents=(
        Document(
            document_id="doc_spec_ja",
            source_path="specs/2026-筐体仕様.md",
            section="仕様",
            paragraphs=(
                "本仕様書は筐体の要求事項を定める。改訂履歴は末尾に付す。",
                "外形寸法の公差は {{F:tolerance}}±0.02mm{{/F}}、"
                "質量は {{F:mass}}2.4kg{{/F}} 以下とする。",
                "動作温度範囲は {{F:temp}}-20℃{{/F}} から {{F:temp_max}}60℃{{/F}} とする。",
                "適用規格は {{F:standard}}ISO 9001{{/F}}、"
                "図面番号は {{F:drawing}}第4図{{/F}} を参照。",
                "組立手順および検査要領については別冊を参照すること。",
            ),
        ),
        Document(
            document_id="doc_rev_ja",
            source_path="specs/2026-改訂通知.md",
            section="改訂",
            paragraphs=(
                "本通知は上記仕様の改訂を伝えるものである。",
                "版数は {{F:version}}1.2.3{{/F}}、"
                "適用開始は {{F:from}}2026年8月30日{{/F}} とする。",
            ),
        ),
    ),
    sentences=(
        S(K.GROUNDED, "外形寸法の公差は±0.02mmです。", "±0.02mm", "tolerance"),
        S(K.GROUNDED, "質量は2.4kg以下と定められています。", "2.4kg", "mass"),
        S(K.GROUNDED, "適用規格はISO 9001です。", "ISO 9001", "standard"),
        S(K.GROUNDED, "版数は1.2.3で、適用開始は2026年8月30日です。", "1.2.3", "version"),
        S(K.DIGIT_DRIFT, "外形寸法の公差は±0.2mmです。", "±0.2mm", "tolerance"),
        S(K.DIGIT_DRIFT, "質量は2.6kg以下と定められています。", "2.6kg", "mass"),
        S(K.DIGIT_DRIFT, "適用開始は2026年8月13日です。", "2026年8月13日", "from"),
        S(K.UNIT_SWAP, "質量は2.4g以下と定められています。", "2.4g", "mass"),
        S(K.UNIT_SWAP, "動作温度の上限は60℉です。", "60℉", "temp_max"),
        S(K.INVENTED_PARTICULAR, "耐圧は 350kPa と規定されています。", "350kPa"),
        S(K.INVENTED_PARTICULAR, "適用規格には ISO 14001 も含まれます。", "ISO 14001"),
        S(K.DERIVED_VALUE, "動作温度の幅は80℃です。", "80℃"),
        S(K.ENTITY_SWAP, "図面番号は第9図を参照してください。", "第9図"),
        S(K.ENTITY_SWAP, "質量の上限は1.2kgです。", "1.2kg"),
        S(
            K.CROSS_DOCUMENT_STITCH,
            "版数1.2.3において、公差は±0.02mmに変更されました。",
            expect_verdict="grounded",
        ),
        S(K.NEGATION_FLIP, "質量は2.4kg以下とは定められていません。", expect_verdict="grounded"),
        S(K.NEGATION_FLIP, "公差についての規定はありません。", expect_verdict="unbearing"),
        S(K.FAITHFUL_PARAPHRASE, "寸法についてはかなり厳しい要求が置かれています。"),
        S(K.FAITHFUL_PARAPHRASE, "重量の上限が設けられている点は設計上の制約になります。"),
    ),
)

_PROTECTED = GenreSpec(
    language="ja",
    genre="protected",
    question="担当者と期限は?",
    documents=(
        Document(
            document_id="doc_case_ja",
            source_path="cases/2026-08-担当表.md",
            section="担当",
            paragraphs=(
                "案件ごとの担当と期限の一覧である。",
                "担当は <PERSON_001>、期限は {{F:deadline}}2026年8月30日{{/F}} とする。",
            ),
        ),
    ),
    sentences=(
        S(K.PLACEHOLDER_RESIDUE, "担当は<PERSON_001>で、期限は2026年8月30日です。", "<PERSON_001>"),
        S(K.PLACEHOLDER_RESIDUE, "<PERSON_001>が本件を引き継ぎます。", "<PERSON_001>"),
    ),
    protected=True,
    tier=(),
)

JAPANESE: tuple[GenreSpec, ...] = (_CONTRACT, _CLINICAL, _SPEC, _PROTECTED)
