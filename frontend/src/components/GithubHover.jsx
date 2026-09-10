import React, { useState } from 'react';

const REPO_URL = 'https://github.com/karthikvvk/medcare-ai';

export default function GithubHover() {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e) => {
    e.preventDefault();
    e.stopPropagation();
    navigator.clipboard.writeText(REPO_URL).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="github-hover-container">
      {/* Floating preview card shown on hover / focus */}
      <div className="github-hover-card" role="tooltip" aria-hidden="false">
        <div className="github-hover-card-header">
          <i className="fa-brands fa-github github-hover-card-icon" />
          <div className="github-hover-card-meta">
            <span className="github-hover-card-title">MedCare AI Repository</span>
            <span className="github-hover-card-branch">main · open source</span>
          </div>
        </div>

        <div className="github-hover-card-url-wrap">
          <code className="github-hover-card-url">{REPO_URL}</code>
          <button
            type="button"
            className="github-hover-copy-btn"
            onClick={handleCopy}
            title="Copy GitHub URL"
            aria-label="Copy GitHub URL to clipboard"
          >
            <i className={`fa-solid ${copied ? 'fa-check' : 'fa-copy'}`} />
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>

        <div className="github-hover-card-footer">
          <span className="github-hover-card-hint">
            <i className="fa-solid fa-code-commit" /> karthikvvk/medcare-ai
          </span>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="github-hover-card-link"
          >
            <span>Visit</span>
            <i className="fa-solid fa-arrow-up-right-from-square" />
          </a>
        </div>
      </div>

      {/* Floating button at the bottom right */}
      <a
        href={REPO_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="github-hover-pill"
        title="View GitHub Repository"
        aria-label="View MedCare AI repository on GitHub"
      >
        <span className="github-hover-status-dot" />
        <i className="fa-brands fa-github github-hover-icon" />
        <span className="github-hover-label">GitHub</span>
        <i className="fa-solid fa-arrow-up-right-from-square github-hover-arrow" />
      </a>
    </div>
  );
}
