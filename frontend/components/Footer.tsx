export function Footer({ wide = false }: { wide?: boolean }) {
  return (
    <footer className="shrink-0 border-t border-rule">
      <div className={`${wide ? "" : "max-w-[1220px]"} mx-auto px-4 sm:px-6 py-4 flex flex-wrap gap-x-6 gap-y-1 justify-between text-[12px] text-ink-3`}>
        <p>Data: ICIJ Offshore Leaks Database &amp; OpenSanctions — possible links, not findings of wrongdoing.</p>
        <p>Powered by <span className="text-ink-2 font-medium">FalkorDB</span></p>
      </div>
    </footer>
  );
}
