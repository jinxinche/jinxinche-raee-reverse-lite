// Headless export for the synthetic dev ELF. Output is an observation, not a proof.
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;

import java.io.FileWriter;
import java.io.PrintWriter;

public class ExportDevSample extends GhidraScript {
    @Override
    public void run() throws Exception {
        String out = System.getenv("RRL_GHIDRA_OUT");
        if (out == null || out.isEmpty()) {
            throw new IllegalStateException("RRL_GHIDRA_OUT is required");
        }
        PrintWriter writer = new PrintWriter(new FileWriter(out));
        writer.println("program=" + currentProgram.getName());
        writer.println("language=" + currentProgram.getLanguageID());
        FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        boolean sawMain = false;
        boolean decompiledMain = false;
        while (functions.hasNext() && !monitor.isCancelled()) {
            Function function = functions.next();
            writer.println("function\t" + function.getName() + "\t" + function.getEntryPoint());
            String name = function.getName();
            if (name.equals("main") || name.equals("checksum")) {
                if (name.equals("main")) {
                    sawMain = true;
                }
                DecompileResults results = decompiler.decompileFunction(function, 30, monitor);
                writer.println("decompile_begin\t" + name);
                if (results.decompileCompleted() && results.getDecompiledFunction() != null) {
                    writer.println(results.getDecompiledFunction().getC());
                    if (name.equals("main")) {
                        decompiledMain = true;
                    }
                } else {
                    writer.println("DECOMPILE_INCOMPLETE");
                }
                writer.println("decompile_end\t" + name);
            }
        }
        decompiler.dispose();
        writer.println("saw_main=" + sawMain);
        writer.println("decompiled_main=" + decompiledMain);
        writer.close();
    }
}
