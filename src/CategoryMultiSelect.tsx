export interface CategoryOption {
  label: string;
  value: string;
  subs?: { label: string; value: string }[];
}

interface Props {
  options: CategoryOption[];
  value: string[];
  onChange: (value: string[]) => void;
}

export default function CategoryMultiSelect({ options, value, onChange }: Props) {
  // Flat list of all subcategories for multi-select
  const allSubs = options.flatMap(cat =>
    (cat.subs || []).map(sub => ({
      label: `${cat.label} / ${sub.label}`,
      value: `${cat.value}::${sub.value}`
    }))
  );

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selected = Array.from(e.target.selectedOptions, opt => opt.value);
    onChange(selected);
  };

  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-gray-700 mb-1">Categorie (multi-selezione)</label>
      <select
        multiple
        className="w-full p-2 border rounded-md h-48"
        value={value}
        onChange={handleChange}
      >
        {allSubs.map(opt => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
