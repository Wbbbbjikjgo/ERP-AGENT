"use client";

interface Props {
  show: boolean;
  onToggle: (v: boolean) => void;
}

export default function ToolCallToggle({ show, onToggle }: Props) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <span className="text-xs text-gray-500">显示工具调用</span>
      <button
        role="switch"
        aria-checked={show}
        onClick={() => onToggle(!show)}
        className={`relative w-8 h-[18px] rounded-full transition-colors ${
          show ? "bg-[#2563EB]" : "bg-gray-300"
        }`}
      >
        <span
          className={`absolute top-[2px] w-[14px] h-[14px] rounded-full bg-white shadow transition-transform ${
            show ? "left-[16px]" : "left-[2px]"
          }`}
        />
      </button>
    </label>
  );
}
