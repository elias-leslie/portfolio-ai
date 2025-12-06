import { cn } from "@/lib/utils";

interface PageContainerProps extends React.HTMLAttributes<HTMLDivElement> {
    children: React.ReactNode;
    fullWidth?: boolean;
}

export function PageContainer({
    children,
    className,
    fullWidth = false,
    ...props
}: PageContainerProps) {
    return (
        <div className="min-h-screen bg-bg">
            <div
                className={cn(
                    "mx-auto space-y-8 px-4 py-8 sm:px-6 lg:px-8",
                    !fullWidth && "max-w-7xl",
                    className
                )}
                {...props}
            >
                {children}
            </div>
        </div>
    );
}
