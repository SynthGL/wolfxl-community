use std::fmt;

#[derive(Debug)]
pub enum Error {
    Io(std::io::Error),
    Xlsx(String),
    Format(String),
    SheetNotFound(String),
    InvalidRange(String),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Io(e) => write!(f, "io error: {e}"),
            Error::Xlsx(s) => write!(f, "xlsx error: {s}"),
            Error::Format(s) => write!(f, "format error: {s}"),
            Error::SheetNotFound(s) => write!(f, "sheet not found: {s:?}"),
            Error::InvalidRange(s) => write!(f, "invalid range: {s}"),
        }
    }
}

impl std::error::Error for Error {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Error::Io(e) => Some(e),
            _ => None,
        }
    }
}

impl From<std::io::Error> for Error {
    fn from(e: std::io::Error) -> Self {
        Error::Io(e)
    }
}

pub type Result<T> = std::result::Result<T, Error>;
