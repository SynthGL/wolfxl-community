//! `<dataValidations>` emitter for worksheet XML.

use crate::model::validation::{ErrorStyle, ValidationOperator, ValidationType};
use crate::model::worksheet::Worksheet;
use crate::xml_escape;

/// Emit `<dataValidations count="N">…</dataValidations>`.
///
/// The caller is responsible for invoking this at CT_Worksheet slot 18,
/// between conditional formatting and hyperlinks.
pub fn emit(out: &mut String, sheet: &Worksheet) {
    if sheet.validations.is_empty() {
        return;
    }

    out.push_str(&format!(
        "<dataValidations count=\"{}\">",
        sheet.validations.len()
    ));

    for dv in &sheet.validations {
        let type_str = match dv.validation_type {
            ValidationType::Any => "any",
            ValidationType::Whole => "whole",
            ValidationType::Decimal => "decimal",
            ValidationType::List => "list",
            ValidationType::Date => "date",
            ValidationType::Time => "time",
            ValidationType::TextLength => "textLength",
            ValidationType::Custom => "custom",
        };

        out.push_str(&format!("<dataValidation type=\"{}\"", type_str));

        let needs_operator = !matches!(
            dv.validation_type,
            ValidationType::List | ValidationType::Custom
        );
        if needs_operator {
            let op_str = match dv.operator {
                ValidationOperator::Between => "between",
                ValidationOperator::NotBetween => "notBetween",
                ValidationOperator::Equal => "equal",
                ValidationOperator::NotEqual => "notEqual",
                ValidationOperator::GreaterThan => "greaterThan",
                ValidationOperator::LessThan => "lessThan",
                ValidationOperator::GreaterThanOrEqual => "greaterThanOrEqual",
                ValidationOperator::LessThanOrEqual => "lessThanOrEqual",
            };
            out.push_str(&format!(" operator=\"{}\"", op_str));
        }

        if dv.allow_blank {
            out.push_str(" allowBlank=\"1\"");
        }
        if dv.show_dropdown {
            out.push_str(" showDropDown=\"1\"");
        }
        if dv.show_input_message {
            out.push_str(" showInputMessage=\"1\"");
        }
        if dv.show_error_message {
            out.push_str(" showErrorMessage=\"1\"");
        }

        match dv.error_style {
            ErrorStyle::Stop => {}
            ErrorStyle::Warning => {
                out.push_str(" errorStyle=\"warning\"");
            }
            ErrorStyle::Information => {
                out.push_str(" errorStyle=\"information\"");
            }
        }

        if let Some(ref title) = dv.error_title {
            out.push_str(&format!(" errorTitle=\"{}\"", xml_escape::attr(title)));
        }
        if let Some(ref msg) = dv.error_message {
            out.push_str(&format!(" error=\"{}\"", xml_escape::attr(msg)));
        }
        if let Some(ref title) = dv.input_title {
            out.push_str(&format!(" promptTitle=\"{}\"", xml_escape::attr(title)));
        }
        if let Some(ref msg) = dv.input_message {
            out.push_str(&format!(" prompt=\"{}\"", xml_escape::attr(msg)));
        }

        out.push_str(&format!(" sqref=\"{}\">", xml_escape::attr(&dv.sqref)));

        if let Some(ref formula) = dv.formula_a {
            out.push_str(&format!(
                "<formula1>{}</formula1>",
                xml_escape::text(formula)
            ));
        }

        let is_between = matches!(
            dv.operator,
            ValidationOperator::Between | ValidationOperator::NotBetween
        );
        if is_between {
            if let Some(ref formula) = dv.formula_b {
                out.push_str(&format!(
                    "<formula2>{}</formula2>",
                    xml_escape::text(formula)
                ));
            }
        }

        out.push_str("</dataValidation>");
    }

    out.push_str("</dataValidations>");
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::validation::DataValidation;

    fn make_dv(
        sqref: &str,
        validation_type: ValidationType,
        operator: ValidationOperator,
        formula_a: Option<&str>,
        formula_b: Option<&str>,
    ) -> DataValidation {
        DataValidation {
            sqref: sqref.to_string(),
            validation_type,
            operator,
            formula_a: formula_a.map(str::to_string),
            formula_b: formula_b.map(str::to_string),
            allow_blank: false,
            show_dropdown: false,
            show_error_message: false,
            error_style: ErrorStyle::Stop,
            error_title: None,
            error_message: None,
            show_input_message: false,
            input_title: None,
            input_message: None,
        }
    }

    fn emit_validations(sheet: &Worksheet) -> String {
        let mut out = String::new();
        emit(&mut out, sheet);
        out
    }

    fn first_data_validation_tag(xml: &str) -> &str {
        let start = xml.find("<dataValidation").expect("dataValidation");
        let end = xml[start..].find('>').expect(">") + start;
        &xml[start..=end]
    }

    #[test]
    fn absent_when_no_validations() {
        let sheet = Worksheet::new("S");
        let xml = emit_validations(&sheet);
        assert_eq!(xml, "");
    }

    #[test]
    fn list_with_literal_string_omits_operator() {
        let mut sheet = Worksheet::new("S");
        sheet.validations.push(make_dv(
            "A1:A10",
            ValidationType::List,
            ValidationOperator::Between,
            Some("\"Red,Green,Blue\""),
            None,
        ));

        let xml = emit_validations(&sheet);

        assert!(xml.contains("<dataValidations count=\"1\">"), "{xml}");
        assert!(xml.contains("<dataValidation type=\"list\""), "{xml}");
        assert!(xml.contains("sqref=\"A1:A10\""), "{xml}");
        assert!(
            xml.contains("<formula1>\"Red,Green,Blue\"</formula1>"),
            "{xml}"
        );
        assert!(
            !first_data_validation_tag(&xml).contains("operator="),
            "{xml}"
        );
    }

    #[test]
    fn list_with_range_reference() {
        let mut sheet = Worksheet::new("S");
        sheet.validations.push(make_dv(
            "B1:B5",
            ValidationType::List,
            ValidationOperator::Between,
            Some("Sheet2!$A$1:$A$5"),
            None,
        ));

        let xml = emit_validations(&sheet);

        assert!(
            xml.contains("<formula1>Sheet2!$A$1:$A$5</formula1>"),
            "{xml}"
        );
    }

    #[test]
    fn whole_between_emits_two_formulas() {
        let mut sheet = Worksheet::new("S");
        sheet.validations.push(make_dv(
            "C1",
            ValidationType::Whole,
            ValidationOperator::Between,
            Some("1"),
            Some("100"),
        ));

        let xml = emit_validations(&sheet);

        assert!(xml.contains("operator=\"between\""), "{xml}");
        assert!(xml.contains("<formula1>1</formula1>"), "{xml}");
        assert!(xml.contains("<formula2>100</formula2>"), "{xml}");
    }

    #[test]
    fn whole_greater_than_emits_one_formula() {
        let mut sheet = Worksheet::new("S");
        sheet.validations.push(make_dv(
            "D1",
            ValidationType::Whole,
            ValidationOperator::GreaterThan,
            Some("0"),
            None,
        ));

        let xml = emit_validations(&sheet);

        assert!(xml.contains("operator=\"greaterThan\""), "{xml}");
        assert!(xml.contains("<formula1>0</formula1>"), "{xml}");
        assert!(!xml.contains("<formula2>"), "{xml}");
    }

    #[test]
    fn custom_formula_omits_operator() {
        let mut sheet = Worksheet::new("S");
        sheet.validations.push(make_dv(
            "E1",
            ValidationType::Custom,
            ValidationOperator::Between,
            Some("A1>0"),
            None,
        ));

        let xml = emit_validations(&sheet);

        assert!(xml.contains("type=\"custom\""), "{xml}");
        assert!(
            !first_data_validation_tag(&xml).contains("operator="),
            "{xml}"
        );
        assert!(xml.contains("<formula1>A1&gt;0</formula1>"), "{xml}");
    }

    #[test]
    fn error_style_warning_emits_error_attrs() {
        let mut sheet = Worksheet::new("S");
        let mut dv = make_dv(
            "F1",
            ValidationType::Whole,
            ValidationOperator::Between,
            Some("0"),
            Some("100"),
        );
        dv.error_style = ErrorStyle::Warning;
        dv.error_title = Some("Oops".into());
        dv.error_message = Some("Invalid".into());
        sheet.validations.push(dv);

        let xml = emit_validations(&sheet);

        assert!(xml.contains("errorStyle=\"warning\""), "{xml}");
        assert!(xml.contains("errorTitle=\"Oops\""), "{xml}");
        assert!(xml.contains("error=\"Invalid\""), "{xml}");
    }

    #[test]
    fn show_flags_and_prompt_error_attrs() {
        let mut sheet = Worksheet::new("S");
        let mut dv = make_dv(
            "G1",
            ValidationType::Any,
            ValidationOperator::Between,
            None,
            None,
        );
        dv.allow_blank = true;
        dv.show_dropdown = true;
        dv.show_input_message = true;
        dv.show_error_message = true;
        dv.input_title = Some("Pick".into());
        dv.input_message = Some("Choose carefully".into());
        dv.error_title = Some("Nope".into());
        dv.error_message = Some("Try again".into());
        sheet.validations.push(dv);

        let xml = emit_validations(&sheet);

        assert!(xml.contains("allowBlank=\"1\""), "{xml}");
        assert!(xml.contains("showDropDown=\"1\""), "{xml}");
        assert!(xml.contains("showInputMessage=\"1\""), "{xml}");
        assert!(xml.contains("showErrorMessage=\"1\""), "{xml}");
        assert!(xml.contains("promptTitle=\"Pick\""), "{xml}");
        assert!(xml.contains("prompt=\"Choose carefully\""), "{xml}");
        assert!(xml.contains("errorTitle=\"Nope\""), "{xml}");
        assert!(xml.contains("error=\"Try again\""), "{xml}");
    }

    #[test]
    fn false_show_flags_are_omitted() {
        let mut sheet = Worksheet::new("S");
        sheet.validations.push(make_dv(
            "G1",
            ValidationType::Any,
            ValidationOperator::Between,
            None,
            None,
        ));

        let xml = emit_validations(&sheet);

        assert!(!xml.contains("allowBlank="), "{xml}");
        assert!(!xml.contains("showDropDown="), "{xml}");
        assert!(!xml.contains("showInputMessage="), "{xml}");
        assert!(!xml.contains("showErrorMessage="), "{xml}");
    }
}
