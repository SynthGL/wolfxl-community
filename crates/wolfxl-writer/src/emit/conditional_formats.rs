//! `<conditionalFormatting>` emitter for worksheet XML.

use crate::model::conditional::{CellIsOperator, ConditionalKind, ConditionalThreshold};
use crate::model::worksheet::Worksheet;
use crate::xml_escape;

/// Emit all supported conditional-formatting blocks for a worksheet.
///
pub fn emit(out: &mut String, sheet: &Worksheet) {
    if sheet.conditional_formats.is_empty() {
        return;
    }

    for cf in &sheet.conditional_formats {
        let mut rules_buf = String::new();

        for (priority_0, rule) in cf.rules.iter().enumerate() {
            // G14: prefer the user-supplied priority when set so rule
            // authors can place high-priority CF rules before lower ones
            // regardless of insertion order. Falls back to positional
            // index (1-based) when not set, preserving prior behaviour.
            let priority = rule.priority.map(|p| p as usize).unwrap_or(priority_0 + 1);

            match &rule.kind {
                ConditionalKind::CellIs {
                    operator,
                    formula_a,
                    formula_b,
                } => {
                    let op_str = match operator {
                        CellIsOperator::Equal => "equal",
                        CellIsOperator::NotEqual => "notEqual",
                        CellIsOperator::GreaterThan => "greaterThan",
                        CellIsOperator::GreaterThanOrEqual => "greaterThanOrEqual",
                        CellIsOperator::LessThan => "lessThan",
                        CellIsOperator::LessThanOrEqual => "lessThanOrEqual",
                        CellIsOperator::Between => "between",
                        CellIsOperator::NotBetween => "notBetween",
                    };

                    rules_buf.push_str(&format!(
                        "<cfRule type=\"cellIs\" priority=\"{}\" operator=\"{}\"",
                        priority, op_str
                    ));
                    if let Some(dxf_id) = rule.dxf_id {
                        rules_buf.push_str(&format!(" dxfId=\"{}\"", dxf_id));
                    }
                    if rule.stop_if_true {
                        rules_buf.push_str(" stopIfTrue=\"1\"");
                    }
                    rules_buf.push('>');
                    rules_buf.push_str(&format!(
                        "<formula>{}</formula>",
                        xml_escape::text(formula_a)
                    ));
                    if matches!(
                        operator,
                        CellIsOperator::Between | CellIsOperator::NotBetween
                    ) {
                        if let Some(fb) = formula_b {
                            rules_buf
                                .push_str(&format!("<formula>{}</formula>", xml_escape::text(fb)));
                        }
                    }
                    rules_buf.push_str("</cfRule>");
                }

                ConditionalKind::Expression { formula } => {
                    rules_buf.push_str(&format!(
                        "<cfRule type=\"expression\" priority=\"{}\"",
                        priority
                    ));
                    if let Some(dxf_id) = rule.dxf_id {
                        rules_buf.push_str(&format!(" dxfId=\"{}\"", dxf_id));
                    }
                    if rule.stop_if_true {
                        rules_buf.push_str(" stopIfTrue=\"1\"");
                    }
                    rules_buf.push('>');
                    rules_buf
                        .push_str(&format!("<formula>{}</formula>", xml_escape::text(formula)));
                    rules_buf.push_str("</cfRule>");
                }

                ConditionalKind::DataBar {
                    color_rgb,
                    min,
                    max,
                    show_value,
                    min_length,
                    max_length,
                } => {
                    rules_buf.push_str(&format!(
                        "<cfRule type=\"dataBar\" priority=\"{}\">",
                        priority
                    ));
                    // OOXML default for showValue is true; only emit the
                    // attribute when it's been explicitly turned off (G12).
                    rules_buf.push_str("<dataBar");
                    if !*show_value {
                        rules_buf.push_str(" showValue=\"0\"");
                    }
                    if let Some(value) = min_length {
                        rules_buf.push_str(&format!(" minLength=\"{}\"", value));
                    }
                    if let Some(value) = max_length {
                        rules_buf.push_str(&format!(" maxLength=\"{}\"", value));
                    }
                    rules_buf.push('>');
                    emit_cfvo(&mut rules_buf, min);
                    emit_cfvo(&mut rules_buf, max);
                    rules_buf.push_str(&format!("<color rgb=\"{}\"/>", color_rgb));
                    rules_buf.push_str("</dataBar>");
                    rules_buf.push_str("</cfRule>");
                }

                ConditionalKind::ColorScale { stops } => {
                    rules_buf.push_str(&format!(
                        "<cfRule type=\"colorScale\" priority=\"{}\">",
                        priority
                    ));
                    rules_buf.push_str("<colorScale>");
                    for stop in stops {
                        emit_cfvo(&mut rules_buf, &stop.threshold);
                    }
                    for stop in stops {
                        rules_buf.push_str(&format!("<color rgb=\"{}\"/>", stop.color_rgb));
                    }
                    rules_buf.push_str("</colorScale>");
                    rules_buf.push_str("</cfRule>");
                }

                ConditionalKind::ContainsText { text } => emit_generic_rule(
                    &mut rules_buf,
                    "containsText",
                    priority,
                    rule.dxf_id,
                    rule.stop_if_true,
                    &[("operator", "containsText"), ("text", text.as_str())],
                    &[],
                ),
                ConditionalKind::NotContainsText { text } => emit_generic_rule(
                    &mut rules_buf,
                    "notContainsText",
                    priority,
                    rule.dxf_id,
                    rule.stop_if_true,
                    &[("operator", "notContains"), ("text", text.as_str())],
                    &[],
                ),
                ConditionalKind::BeginsWith { text } => emit_generic_rule(
                    &mut rules_buf,
                    "beginsWith",
                    priority,
                    rule.dxf_id,
                    rule.stop_if_true,
                    &[("operator", "beginsWith"), ("text", text.as_str())],
                    &[],
                ),
                ConditionalKind::EndsWith { text } => emit_generic_rule(
                    &mut rules_buf,
                    "endsWith",
                    priority,
                    rule.dxf_id,
                    rule.stop_if_true,
                    &[("operator", "endsWith"), ("text", text.as_str())],
                    &[],
                ),
                ConditionalKind::Duplicate => {
                    emit_generic_rule(
                        &mut rules_buf,
                        "duplicateValues",
                        priority,
                        rule.dxf_id,
                        rule.stop_if_true,
                        &[],
                        &[],
                    );
                }
                ConditionalKind::Unique => {
                    emit_generic_rule(
                        &mut rules_buf,
                        "uniqueValues",
                        priority,
                        rule.dxf_id,
                        rule.stop_if_true,
                        &[],
                        &[],
                    );
                }
                ConditionalKind::Top10 {
                    count,
                    bottom,
                    percent,
                } => {
                    let rank = count.to_string();
                    let bottom_value = if *bottom { "1" } else { "0" };
                    let percent_value = if *percent { "1" } else { "0" };
                    emit_generic_rule(
                        &mut rules_buf,
                        "top10",
                        priority,
                        rule.dxf_id,
                        rule.stop_if_true,
                        &[
                            ("rank", rank.as_str()),
                            ("bottom", bottom_value),
                            ("percent", percent_value),
                        ],
                        &[],
                    );
                }
                ConditionalKind::AboveAverage { above, std_dev } => {
                    let above_value = if *above { "1" } else { "0" };
                    let std_dev_value = std_dev.to_string();
                    let attrs = if *std_dev > 0 {
                        vec![
                            ("aboveAverage", above_value),
                            ("stdDev", std_dev_value.as_str()),
                        ]
                    } else {
                        vec![("aboveAverage", above_value)]
                    };
                    emit_generic_rule(
                        &mut rules_buf,
                        "aboveAverage",
                        priority,
                        rule.dxf_id,
                        rule.stop_if_true,
                        &attrs,
                        &[],
                    );
                }
                ConditionalKind::IconSet {
                    set_name,
                    thresholds,
                    show_value,
                    percent,
                    reverse,
                } => {
                    // G11: emit `<cfRule type="iconSet">` with an inner
                    // `<iconSet iconSet="..." [showValue="0"]>` element
                    // wrapping one `<cfvo>` per icon band. Unlike
                    // dataBar/colorScale, iconSet does NOT carry inline
                    // `<color>` elements.
                    rules_buf.push_str(&format!(
                        "<cfRule type=\"iconSet\" priority=\"{}\"",
                        priority
                    ));
                    if rule.stop_if_true {
                        rules_buf.push_str(" stopIfTrue=\"1\"");
                    }
                    rules_buf.push('>');

                    rules_buf.push_str(&format!(
                        "<iconSet iconSet=\"{}\"",
                        xml_escape::attr(set_name)
                    ));
                    if !*show_value {
                        // OOXML default is showValue="1" — only emit when
                        // explicitly false.
                        rules_buf.push_str(" showValue=\"0\"");
                    }
                    if let Some(value) = percent {
                        rules_buf.push_str(if *value {
                            " percent=\"1\""
                        } else {
                            " percent=\"0\""
                        });
                    }
                    if let Some(value) = reverse {
                        rules_buf.push_str(if *value {
                            " reverse=\"1\""
                        } else {
                            " reverse=\"0\""
                        });
                    }
                    rules_buf.push('>');
                    for threshold in thresholds {
                        emit_cfvo(&mut rules_buf, threshold);
                    }
                    rules_buf.push_str("</iconSet>");
                    rules_buf.push_str("</cfRule>");
                }
                ConditionalKind::Generic {
                    type_name,
                    attrs,
                    formulas,
                } => {
                    let attr_pairs: Vec<(&str, &str)> = attrs
                        .iter()
                        .map(|(k, v)| (k.as_str(), v.as_str()))
                        .collect();
                    emit_generic_rule(
                        &mut rules_buf,
                        type_name,
                        priority,
                        rule.dxf_id,
                        rule.stop_if_true,
                        &attr_pairs,
                        formulas,
                    );
                }
            }
        }

        if !rules_buf.is_empty() {
            out.push_str(&format!(
                "<conditionalFormatting sqref=\"{}\">",
                xml_escape::attr(&cf.sqref)
            ));
            out.push_str(&rules_buf);
            out.push_str("</conditionalFormatting>");
        }
    }
}

fn emit_generic_rule(
    out: &mut String,
    type_name: &str,
    priority: usize,
    dxf_id: Option<u32>,
    stop_if_true: bool,
    attrs: &[(&str, &str)],
    formulas: &[String],
) {
    out.push_str(&format!(
        "<cfRule type=\"{}\" priority=\"{}\"",
        xml_escape::attr(type_name),
        priority
    ));
    for (name, value) in attrs {
        if value.is_empty() {
            continue;
        }
        out.push_str(&format!(
            " {}=\"{}\"",
            xml_escape::attr(name),
            xml_escape::attr(value)
        ));
    }
    if let Some(dxf_id) = dxf_id {
        out.push_str(&format!(" dxfId=\"{}\"", dxf_id));
    }
    if stop_if_true {
        out.push_str(" stopIfTrue=\"1\"");
    }
    if formulas.is_empty() {
        out.push_str("/>");
        return;
    }
    out.push('>');
    for formula in formulas {
        out.push_str(&format!("<formula>{}</formula>", xml_escape::text(formula)));
    }
    out.push_str("</cfRule>");
}

fn emit_cfvo(out: &mut String, threshold: &ConditionalThreshold) {
    match threshold {
        ConditionalThreshold::Min => {
            out.push_str("<cfvo type=\"min\"/>");
        }
        ConditionalThreshold::Max => {
            out.push_str("<cfvo type=\"max\"/>");
        }
        ConditionalThreshold::Number(x) => {
            out.push_str(&format!("<cfvo type=\"num\" val=\"{}\"/>", format_f64(*x)));
        }
        ConditionalThreshold::Percent(x) => {
            out.push_str(&format!(
                "<cfvo type=\"percent\" val=\"{}\"/>",
                format_f64(*x)
            ));
        }
        ConditionalThreshold::Percentile(x) => {
            out.push_str(&format!(
                "<cfvo type=\"percentile\" val=\"{}\"/>",
                format_f64(*x)
            ));
        }
        ConditionalThreshold::Formula(s) => {
            out.push_str(&format!(
                "<cfvo type=\"formula\" val=\"{}\"/>",
                xml_escape::attr(s)
            ));
        }
    }
}

fn format_f64(n: f64) -> String {
    if n == (n as i64) as f64 && n.abs() < 1e15 {
        format!("{}", n as i64)
    } else {
        format!("{}", n)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::conditional::{ColorScaleStop, ConditionalFormat, ConditionalRule};
    use quick_xml::events::Event;
    use quick_xml::Reader;

    fn rule(kind: ConditionalKind) -> ConditionalRule {
        ConditionalRule {
            kind,
            dxf_id: None,
            stop_if_true: false,
            priority: None,
        }
    }

    fn styled_rule(
        kind: ConditionalKind,
        dxf_id: Option<u32>,
        stop_if_true: bool,
    ) -> ConditionalRule {
        ConditionalRule {
            kind,
            dxf_id,
            stop_if_true,
            priority: None,
        }
    }

    fn rule_with_priority(kind: ConditionalKind, priority: Option<u32>) -> ConditionalRule {
        ConditionalRule {
            kind,
            dxf_id: None,
            stop_if_true: false,
            priority,
        }
    }

    fn cf(sqref: &str, rules: Vec<ConditionalRule>) -> ConditionalFormat {
        ConditionalFormat {
            sqref: sqref.into(),
            rules,
        }
    }

    fn emit_sheet_fragment(sheet: &Worksheet) -> String {
        let mut out = String::new();
        emit(&mut out, sheet);
        out
    }

    fn emit_one_cf(rules: Vec<ConditionalRule>) -> String {
        let mut sheet = Worksheet::new("S");
        sheet.conditional_formats.push(cf("A1:A10", rules));
        emit_sheet_fragment(&sheet)
    }

    fn assert_fragment_parses(fragment: &str) {
        let wrapped = format!("<root>{fragment}</root>");
        let mut reader = Reader::from_str(&wrapped);
        let mut buf = Vec::new();

        loop {
            match reader.read_event_into(&mut buf) {
                Ok(Event::Eof) => break,
                Err(e) => panic!("XML parse error: {e}; fragment: {fragment}"),
                _ => {}
            }
            buf.clear();
        }
    }

    fn first_cf_rule_tag(xml: &str) -> &str {
        let start = xml.find("<cfRule").expect("cfRule start");
        let end = xml[start..].find('>').expect("cfRule end") + start;
        &xml[start..=end]
    }

    fn contains_text_rule() -> ConditionalRule {
        rule(ConditionalKind::ContainsText {
            text: "late".into(),
        })
    }

    #[test]
    fn absent_when_no_conditional_formats() {
        let sheet = Worksheet::new("S");

        let out = emit_sheet_fragment(&sheet);

        assert!(out.is_empty());
    }

    #[test]
    fn cell_is_greater_than_emits_dxf_id_operator_and_formula() {
        let out = emit_one_cf(vec![styled_rule(
            ConditionalKind::CellIs {
                operator: CellIsOperator::GreaterThan,
                formula_a: "100".into(),
                formula_b: None,
            },
            Some(0),
            false,
        )]);

        assert_fragment_parses(&out);
        assert_eq!(
            out,
            "<conditionalFormatting sqref=\"A1:A10\"><cfRule type=\"cellIs\" priority=\"1\" operator=\"greaterThan\" dxfId=\"0\"><formula>100</formula></cfRule></conditionalFormatting>"
        );
    }

    #[test]
    fn cell_is_between_emits_two_formulas() {
        let out = emit_one_cf(vec![styled_rule(
            ConditionalKind::CellIs {
                operator: CellIsOperator::Between,
                formula_a: "10".into(),
                formula_b: Some("20".into()),
            },
            Some(1),
            false,
        )]);

        assert_fragment_parses(&out);
        assert!(out.contains("operator=\"between\" dxfId=\"1\""));
        assert!(out.contains("<formula>10</formula><formula>20</formula>"));
    }

    #[test]
    fn expression_emits_formula_without_operator_attribute() {
        let out = emit_one_cf(vec![styled_rule(
            ConditionalKind::Expression {
                formula: "A1>B1".into(),
            },
            Some(2),
            false,
        )]);

        assert_fragment_parses(&out);
        let tag = first_cf_rule_tag(&out);
        assert!(tag.contains("type=\"expression\""));
        assert!(tag.contains("dxfId=\"2\""));
        assert!(!tag.contains("operator="), "unexpected operator: {tag}");
        assert!(out.contains("<formula>A1&gt;B1</formula>"));
    }

    #[test]
    fn stop_if_true_emits_attribute_only_when_true() {
        let out = emit_one_cf(vec![
            styled_rule(
                ConditionalKind::Expression {
                    formula: "A1>0".into(),
                },
                None,
                true,
            ),
            styled_rule(
                ConditionalKind::Expression {
                    formula: "A1<0".into(),
                },
                None,
                false,
            ),
        ]);

        assert_fragment_parses(&out);
        assert_eq!(out.matches("stopIfTrue=\"1\"").count(), 1);
        assert!(!out.contains("stopIfTrue=\"0\""));
    }

    #[test]
    fn explicit_priority_overrides_positional_index() {
        // G14: when a rule carries a user-supplied priority, the emitter
        // writes that value instead of the positional fallback. Two rules
        // in the same block should keep their authored ordering.
        let out = emit_one_cf(vec![
            rule_with_priority(
                ConditionalKind::Expression {
                    formula: "A1>0".into(),
                },
                Some(7),
            ),
            rule_with_priority(
                ConditionalKind::Expression {
                    formula: "A1<0".into(),
                },
                Some(3),
            ),
        ]);

        assert_fragment_parses(&out);
        assert!(out.contains("priority=\"7\""), "{out}");
        assert!(out.contains("priority=\"3\""), "{out}");
        // Positional fallback would have written priority=1, priority=2.
        assert!(!out.contains("priority=\"1\""), "{out}");
        assert!(!out.contains("priority=\"2\""), "{out}");
    }

    #[test]
    fn missing_priority_falls_back_to_positional_index() {
        // G14: when no user priority is set, emitter still uses 1-based
        // positional index for backwards compatibility.
        let out = emit_one_cf(vec![rule(ConditionalKind::Expression {
            formula: "A1>0".into(),
        })]);

        assert!(out.contains("priority=\"1\""), "{out}");
    }

    #[test]
    fn data_bar_ignores_dxf_id_and_emits_thresholds_and_color() {
        let out = emit_one_cf(vec![styled_rule(
            ConditionalKind::DataBar {
                color_rgb: "FFFF0000".into(),
                min: ConditionalThreshold::Min,
                max: ConditionalThreshold::Max,
                show_value: true,
                min_length: None,
                max_length: None,
            },
            Some(99),
            false,
        )]);

        assert_fragment_parses(&out);
        let tag = first_cf_rule_tag(&out);
        assert_eq!(tag, "<cfRule type=\"dataBar\" priority=\"1\">");
        assert!(!tag.contains("dxfId"));
        assert!(out.contains(
            "<dataBar><cfvo type=\"min\"/><cfvo type=\"max\"/><color rgb=\"FFFF0000\"/></dataBar>"
        ));
    }

    #[test]
    fn data_bar_emits_length_attrs_when_supplied() {
        let out = emit_one_cf(vec![rule(ConditionalKind::DataBar {
            color_rgb: "FFFF0000".into(),
            min: ConditionalThreshold::Min,
            max: ConditionalThreshold::Max,
            show_value: false,
            min_length: Some(5),
            max_length: Some(90),
        })]);

        assert_fragment_parses(&out);
        assert!(
            out.contains("<dataBar showValue=\"0\" minLength=\"5\" maxLength=\"90\">"),
            "{out}"
        );
    }

    #[test]
    fn color_scale_two_stops_emits_cfvos_before_colors() {
        let out = emit_one_cf(vec![styled_rule(
            ConditionalKind::ColorScale {
                stops: vec![
                    ColorScaleStop {
                        threshold: ConditionalThreshold::Min,
                        color_rgb: "FF0000FF".into(),
                    },
                    ColorScaleStop {
                        threshold: ConditionalThreshold::Max,
                        color_rgb: "FFFF0000".into(),
                    },
                ],
            },
            Some(99),
            false,
        )]);

        assert_fragment_parses(&out);
        let tag = first_cf_rule_tag(&out);
        assert_eq!(tag, "<cfRule type=\"colorScale\" priority=\"1\">");
        assert!(out.contains(
            "<colorScale><cfvo type=\"min\"/><cfvo type=\"max\"/><color rgb=\"FF0000FF\"/><color rgb=\"FFFF0000\"/></colorScale>"
        ));
    }

    #[test]
    fn color_scale_three_stops_emits_all_cfvos_before_all_colors() {
        let out = emit_one_cf(vec![rule(ConditionalKind::ColorScale {
            stops: vec![
                ColorScaleStop {
                    threshold: ConditionalThreshold::Min,
                    color_rgb: "FF0000FF".into(),
                },
                ColorScaleStop {
                    threshold: ConditionalThreshold::Percent(50.0),
                    color_rgb: "FF00FF00".into(),
                },
                ColorScaleStop {
                    threshold: ConditionalThreshold::Max,
                    color_rgb: "FFFF0000".into(),
                },
            ],
        })]);

        assert_fragment_parses(&out);
        assert_eq!(out.matches("<cfvo").count(), 3);
        assert_eq!(out.matches("<color rgb=").count(), 3);
        assert!(out.contains("<cfvo type=\"percent\" val=\"50\"/>"));

        let color_scale_start = out.find("<colorScale>").expect("colorScale");
        let color_scale_end = out.find("</colorScale>").expect("/colorScale");
        let color_scale = &out[color_scale_start..color_scale_end];
        let last_cfvo = color_scale.rfind("<cfvo").expect("last cfvo");
        let first_color = color_scale.find("<color rgb=").expect("first color");
        assert!(last_cfvo < first_color, "{color_scale}");
    }

    #[test]
    fn generic_rule_variants_emit_with_supported_rules() {
        let mut sheet = Worksheet::new("S");
        sheet.conditional_formats.push(cf(
            "A1:A10",
            vec![
                contains_text_rule(),
                rule(ConditionalKind::Expression {
                    formula: "A1>0".into(),
                }),
                rule(ConditionalKind::Duplicate),
            ],
        ));

        let out = emit_sheet_fragment(&sheet);

        assert_fragment_parses(&out);
        assert!(out.contains("<conditionalFormatting sqref=\"A1:A10\">"));
        assert_eq!(out.matches("<cfRule").count(), 3);
        assert!(out.contains(
            "<cfRule type=\"containsText\" priority=\"1\" operator=\"containsText\" text=\"late\"/>"
        ));
        assert!(out.contains("<cfRule type=\"expression\" priority=\"2\">"));
        assert!(out.contains("<cfRule type=\"duplicateValues\" priority=\"3\"/>"));
    }

    #[test]
    fn icon_set_three_traffic_lights_emits_inner_iconset_with_cfvos() {
        let out = emit_one_cf(vec![rule(ConditionalKind::IconSet {
            set_name: "3TrafficLights1".into(),
            thresholds: vec![
                ConditionalThreshold::Percent(0.0),
                ConditionalThreshold::Percent(33.0),
                ConditionalThreshold::Percent(67.0),
            ],
            show_value: true,
            percent: None,
            reverse: None,
        })]);

        assert_fragment_parses(&out);
        let tag = first_cf_rule_tag(&out);
        assert_eq!(tag, "<cfRule type=\"iconSet\" priority=\"1\">");
        // Inner iconSet element with default showValue (no attribute emitted).
        assert!(out.contains("<iconSet iconSet=\"3TrafficLights1\">"));
        assert!(!out.contains("showValue"));
        // One cfvo per icon band; no color elements (unlike dataBar/colorScale).
        assert_eq!(out.matches("<cfvo").count(), 3);
        assert_eq!(out.matches("<color ").count(), 0);
        assert!(out.contains("<cfvo type=\"percent\" val=\"0\"/>"));
        assert!(out.contains("<cfvo type=\"percent\" val=\"33\"/>"));
        assert!(out.contains("<cfvo type=\"percent\" val=\"67\"/>"));
        assert!(out.contains("</iconSet></cfRule>"));
    }

    #[test]
    fn icon_set_show_value_false_emits_attribute() {
        let out = emit_one_cf(vec![rule(ConditionalKind::IconSet {
            set_name: "3TrafficLights1".into(),
            thresholds: vec![
                ConditionalThreshold::Percent(0.0),
                ConditionalThreshold::Percent(33.0),
                ConditionalThreshold::Percent(67.0),
            ],
            show_value: false,
            percent: None,
            reverse: None,
        })]);

        assert_fragment_parses(&out);
        assert!(out.contains("<iconSet iconSet=\"3TrafficLights1\" showValue=\"0\">"));
    }

    #[test]
    fn icon_set_emits_percent_and_reverse_flags() {
        let out = emit_one_cf(vec![rule(ConditionalKind::IconSet {
            set_name: "4Rating".into(),
            thresholds: vec![
                ConditionalThreshold::Number(1.0),
                ConditionalThreshold::Number(3.0),
                ConditionalThreshold::Number(5.0),
                ConditionalThreshold::Number(7.0),
            ],
            show_value: false,
            percent: Some(false),
            reverse: Some(true),
        })]);

        assert_fragment_parses(&out);
        assert!(out
            .contains("<iconSet iconSet=\"4Rating\" showValue=\"0\" percent=\"0\" reverse=\"1\">"));
    }

    #[test]
    fn icon_set_five_arrows_emits_five_cfvos() {
        let out = emit_one_cf(vec![rule(ConditionalKind::IconSet {
            set_name: "5Arrows".into(),
            thresholds: vec![
                ConditionalThreshold::Percent(0.0),
                ConditionalThreshold::Percent(20.0),
                ConditionalThreshold::Percent(40.0),
                ConditionalThreshold::Percent(60.0),
                ConditionalThreshold::Percent(80.0),
            ],
            show_value: true,
            percent: None,
            reverse: None,
        })]);

        assert_fragment_parses(&out);
        assert!(out.contains("<iconSet iconSet=\"5Arrows\">"));
        assert_eq!(out.matches("<cfvo").count(), 5);
    }

    #[test]
    fn icon_set_percentile_thresholds_emit_correct_cfvo_type() {
        let out = emit_one_cf(vec![rule(ConditionalKind::IconSet {
            set_name: "3Arrows".into(),
            thresholds: vec![
                ConditionalThreshold::Percentile(0.0),
                ConditionalThreshold::Percentile(33.0),
                ConditionalThreshold::Percentile(67.0),
            ],
            show_value: true,
            percent: None,
            reverse: None,
        })]);

        assert_fragment_parses(&out);
        assert!(out.contains("<cfvo type=\"percentile\" val=\"33\"/>"));
        assert!(out.contains("<cfvo type=\"percentile\" val=\"67\"/>"));
    }

    #[test]
    fn generic_only_rules_emit_wrapper() {
        let out = emit_one_cf(vec![
            rule(ConditionalKind::Duplicate),
            rule(ConditionalKind::Unique),
            contains_text_rule(),
        ]);

        assert_fragment_parses(&out);
        assert_eq!(out.matches("<cfRule").count(), 3);
        assert!(out.contains("type=\"duplicateValues\""));
        assert!(out.contains("type=\"uniqueValues\""));
        assert!(out.contains("type=\"containsText\""));
    }

    #[test]
    fn supported_kitchen_sink_is_well_formed() {
        let mut sheet = Worksheet::new("Kitchen");
        sheet.conditional_formats.push(cf(
            "A1:D10",
            vec![
                styled_rule(
                    ConditionalKind::CellIs {
                        operator: CellIsOperator::GreaterThan,
                        formula_a: "50".into(),
                        formula_b: None,
                    },
                    Some(0),
                    false,
                ),
                styled_rule(
                    ConditionalKind::Expression {
                        formula: "A1>B1".into(),
                    },
                    Some(1),
                    true,
                ),
                rule(ConditionalKind::DataBar {
                    color_rgb: "FF0070C0".into(),
                    min: ConditionalThreshold::Min,
                    max: ConditionalThreshold::Max,
                    show_value: true,
                    min_length: None,
                    max_length: None,
                }),
                rule(ConditionalKind::ColorScale {
                    stops: vec![
                        ColorScaleStop {
                            threshold: ConditionalThreshold::Min,
                            color_rgb: "FFF8696B".into(),
                        },
                        ColorScaleStop {
                            threshold: ConditionalThreshold::Percentile(50.0),
                            color_rgb: "FFFFEB84".into(),
                        },
                        ColorScaleStop {
                            threshold: ConditionalThreshold::Formula("$D$1".into()),
                            color_rgb: "FF63BE7B".into(),
                        },
                    ],
                }),
            ],
        ));

        let out = emit_sheet_fragment(&sheet);

        assert_fragment_parses(&out);
        assert!(out.starts_with("<conditionalFormatting sqref=\"A1:D10\">"));
        assert_eq!(out.matches("<cfRule").count(), 4);
        assert!(out.contains("<cfvo type=\"percentile\" val=\"50\"/>"));
        assert!(out.contains("<cfvo type=\"formula\" val=\"$D$1\"/>"));
        assert!(out.ends_with("</conditionalFormatting>"));
    }
}
