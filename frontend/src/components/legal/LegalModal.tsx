import React, { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardBody } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { XIcon, ShieldCheckIcon } from '../icons/Icons';
import './LegalModal.css';

export type LegalDocType = 'terms' | 'privacy';

export interface LegalModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialDoc?: LegalDocType;
}

export const LegalModal: React.FC<LegalModalProps> = ({
  isOpen,
  onClose,
  initialDoc = 'terms',
}) => {
  const [activeDoc, setActiveDoc] = useState<LegalDocType>(initialDoc);

  useEffect(() => {
    if (isOpen) {
      setActiveDoc(initialDoc);
    }
  }, [isOpen, initialDoc]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="orq-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="legal-modal-title"
      data-testid="legal-modal"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="orq-modal-container orq-legal-container">
        <Card className="orq-legal-card">
          <CardHeader className="orq-legal-header">
            <div className="orq-legal-title-wrap">
              <div className="orq-legal-icon-wrap" aria-hidden="true">
                <ShieldCheckIcon size={20} />
              </div>
              <div>
                <CardTitle id="legal-modal-title" className="orq-legal-title">
                  {activeDoc === 'terms' ? 'Terms of Service' : 'Privacy Policy'}
                </CardTitle>
                <p className="orq-legal-subtitle">
                  Last updated: 23 November 2026 · Platform Version 0.1.0
                </p>
              </div>
            </div>
            <button
              type="button"
              className="orq-modal-close"
              onClick={onClose}
              aria-label="Close legal modal"
            >
              <XIcon size={20} />
            </button>
          </CardHeader>

          <div className="orq-legal-tabs" role="tablist" aria-label="Legal Documents">
            <button
              type="button"
              role="tab"
              aria-selected={activeDoc === 'terms'}
              className={`orq-legal-tab ${activeDoc === 'terms' ? 'active' : ''}`}
              onClick={() => setActiveDoc('terms')}
            >
              Terms of Service
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeDoc === 'privacy'}
              className={`orq-legal-tab ${activeDoc === 'privacy' ? 'active' : ''}`}
              onClick={() => setActiveDoc('privacy')}
            >
              Privacy Policy
            </button>
          </div>

          <CardBody className="orq-legal-body">
            {activeDoc === 'terms' ? (
              <div className="orq-legal-content" tabIndex={0}>
                <section>
                  <h3>1. Acceptance and Platform Purpose</h3>
                  <p>
                    Orqestra is a specialized business operations, inventory coordination, and human-in-the-loop workflow management platform. By accessing or using the platform, business operators and authorized team members agree to be bound by these Terms of Service.
                  </p>
                </section>

                <section>
                  <h3>2. Tenancy, Data Ownership, and Isolation</h3>
                  <p>
                    Each business created in Orqestra operates within an isolated tenant partition. Customer records, product catalogs, inventory levels, order items, and billing documents are segregated at the database engine level via PostgreSQL Row Level Security (RLS) and cryptographic tenant scoping. Operators retain exclusive ownership of all business operational data.
                  </p>
                </section>

                <section>
                  <h3>3. Account Security and Role-Based Access</h3>
                  <p>
                    Operators are responsible for safeguarding authentication credentials. Orqestra supports granular role-based memberships (<code>owner</code>, <code>admin</code>, and <code>staff</code>). Permissions for stock adjustments, order approvals, and invoice issuance are strictly enforced at both API and database RPC boundaries.
                  </p>
                </section>

                <section>
                  <h3>4. Immutable Ledgers and Audit Traceability</h3>
                  <p>
                    To ensure audit compliance and financial consistency, stock movements, invoice snapshot records, and administrative security events are immutable. Historical invoices retain frozen customer and line-item snapshots at time of issuance, independent of subsequent catalog changes.
                  </p>
                </section>

                <section>
                  <h3>5. Human-in-the-Loop AI Operations</h3>
                  <p>
                    AI-powered intake services parse customer text into candidate orders using schema validation and prompt injection defenses. AI outputs are advisory; authorized human operators retain final review and approval authority before orders or inventory commitments are executed.
                  </p>
                </section>

                <section>
                  <h3>6. Support and Operational Inquiries</h3>
                  <p>
                    For platform support, data export requests, or security inquiries, contact our team at{' '}
                    <a href="mailto:support@orqestra.io" className="orq-legal-link">
                      support@orqestra.io
                    </a>.
                  </p>
                </section>
              </div>
            ) : (
              <div className="orq-legal-content" tabIndex={0}>
                <section>
                  <h3>1. Information We Collect</h3>
                  <p>
                    We collect information necessary to provide business operational services: operator account identifiers (email, authenticated user ID), business profile details (business name, operating currency, slug), customer directories (name, contact, billing address), and catalog transactions.
                  </p>
                </section>

                <section>
                  <h3>2. How We Use Information</h3>
                  <p>
                    Collected data is strictly utilized to deliver real-time inventory management, order processing, invoice generation, and AI-assisted workflow extractions. We never sell operator or customer data to third parties or data brokers.
                  </p>
                </section>

                <section>
                  <h3>3. Infrastructure and Security Controls</h3>
                  <p>
                    Data is stored in managed PostgreSQL databases with mandatory TLS 1.3 encryption in transit (<code>sslmode=verify-full</code>). Access controls utilize Supabase Auth with JWT signature verification and SCRAM-SHA-256 database authentication.
                  </p>
                </section>

                <section>
                  <h3>4. Third-Party Processors</h3>
                  <p>
                    Orqestra integrates with trusted infrastructure providers: Supabase Inc. (cloud database hosting and authentication) and Google Gemini / OpenAI (AI order extraction via secure endpoints, where customer text is processed in-memory for extraction only and not used for public model training).
                  </p>
                </section>

                <section>
                  <h3>5. Data Portability and Deletion</h3>
                  <p>
                    Business owners may request complete export or deletion of their business partition and associated operational records at any time by contacting{' '}
                    <a href="mailto:privacy@orqestra.io" className="orq-legal-link">
                      privacy@orqestra.io
                    </a>.
                  </p>
                </section>
              </div>
            )}
          </CardBody>

          <div className="orq-legal-footer">
            <Badge variant="operational">Security Verified</Badge>
            <Button variant="secondary" size="sm" onClick={onClose}>
              Close Document
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
};
