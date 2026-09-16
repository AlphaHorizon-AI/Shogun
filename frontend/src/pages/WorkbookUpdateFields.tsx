import { FolderOpen, Plus, Trash2 } from 'lucide-react';

export type WorkbookPickerTarget =
  | { key: 'profile_path' | 'template_path' | 'reference_workbook_path' }
  | { key: 'pdf_paths'; index: number };

export interface WorkbookUpdateConfig {
  profile_path?: string;
  template_path?: string;
  reference_workbook_path?: string;
  pdf_paths?: string[] | string;
  sheet_name?: string;
}

interface Props {
  value: WorkbookUpdateConfig;
  onChange: (value: WorkbookUpdateConfig) => void;
  onBrowse: (target: WorkbookPickerTarget) => void;
}

const inputStyle = 'min-w-0 flex-1 rounded-lg border border-[#1a2040] bg-[#0a0e1a] p-2 text-xs text-[#c8d0d8] outline-none focus:border-[#10b981]';
const browseStyle = 'rounded-lg border border-[#10b981]/30 bg-[#10b981]/10 px-2.5 text-[#10b981] hover:bg-[#10b981]/20';

export function WorkbookUpdateFields({ value, onChange, onBrowse }: Props) {
  const pdfs = Array.isArray(value.pdf_paths) ? value.pdf_paths : value.pdf_paths ? [value.pdf_paths] : [];
  const pathFields = [
    { key: 'profile_path', label: 'Rules file', placeholder: 'Input/rules.shogun-profile.json' },
    { key: 'template_path', label: 'Existing Excel workbook', placeholder: 'Input/planning.xlsx' },
    { key: 'reference_workbook_path', label: 'Reference workbook (optional)', placeholder: 'Input/reference.xlsx' },
  ] as const;

  return (
    <div className="space-y-3 rounded-lg border border-[#10b981]/25 bg-[#10b981]/5 p-3">
      <p className="text-[10px] leading-relaxed text-[#a7cbbd]">
        Connect Input → this Files step → Output. This step reads the original PDFs and creates a copy of the Excel workbook. Your rules file determines whether to update an existing plan or fill an empty template. Place the files in the Shogun workspace first. A Samurai extraction step is not needed on this path.
      </p>
      {pathFields.map(({ key, label, placeholder }) => (
        <div key={key} className="space-y-1.5">
          <label className="block text-[9px] font-bold uppercase tracking-widest text-[#7a8899]">
            {label}
            <span className="mt-1.5 flex gap-1.5">
              <input
                className={inputStyle}
                value={value[key] || ''}
                onChange={(event) => onChange({ ...value, [key]: event.target.value })}
                placeholder={placeholder}
                spellCheck={false}
              />
              <button type="button" className={browseStyle} aria-label={`Browse ${label.toLowerCase()}`} onClick={() => onBrowse({ key })}>
                <FolderOpen className="h-3.5 w-3.5" />
              </button>
            </span>
          </label>
        </div>
      ))}
      <div className="space-y-2">
        <p className="text-[9px] font-bold uppercase tracking-widest text-[#7a8899]">Source PDFs (1–10)</p>
        {pdfs.map((path, index) => (
          <div key={index} className="flex gap-1.5">
            <input
              aria-label={`Source PDF ${index + 1}`}
              className={inputStyle}
              value={path}
              placeholder="Input/report.pdf"
              spellCheck={false}
              onChange={(event) => onChange({ ...value, pdf_paths: pdfs.map((item, i) => i === index ? event.target.value : item) })}
            />
            <button type="button" className={browseStyle} aria-label={`Browse source PDF ${index + 1}`} onClick={() => onBrowse({ key: 'pdf_paths', index })}>
              <FolderOpen className="h-3.5 w-3.5" />
            </button>
            <button type="button" aria-label={`Remove source PDF ${index + 1}`} className="rounded p-1 text-[#ef4444] hover:bg-[#ef4444]/10" onClick={() => onChange({ ...value, pdf_paths: pdfs.filter((_, i) => i !== index) })}>
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
        <button type="button" disabled={pdfs.length >= 10} className="flex items-center gap-1 text-[10px] font-bold text-[#10b981] disabled:opacity-40" onClick={() => onChange({ ...value, pdf_paths: [...pdfs, ''] })}>
          <Plus className="h-3.5 w-3.5" /> Add PDF
        </button>
      </div>
      <p className="text-[9px] leading-relaxed text-[#7a8899]">Choose a new destination file below. The result includes reports showing the changes and anything that needs review.</p>
    </div>
  );
}
