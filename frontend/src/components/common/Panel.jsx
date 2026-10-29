export default function Panel({ title, eyebrow, icon: Icon, action, children, className = '' }) {
  return <section className={`panel ${className}`} aria-label={title}>
    <div className="panel-heading"><div className="panel-title">{Icon && <Icon size={19} aria-hidden="true" />}<div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h2>{title}</h2></div></div>{action}</div>
    {children}
  </section>;
}

