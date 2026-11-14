// Headless export of named functions. Output is an observation, not a proof.
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;

import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

public class ExportNamed extends GhidraScript {
    @Override
    public void run() throws Exception {
        String out = System.getenv("RRL_GHIDRA_OUT");
        if (out == null || out.isEmpty()) {
            throw new IllegalStateException("RRL_GHIDRA_OUT is required");
        }
        String wanted = System.getenv("RRL_GHIDRA_FUNCTIONS");
        if (wanted == null || wanted.isEmpty()) {
            wanted = "main";
        }
        Set<String> names = new HashSet<String>(Arrays.asList(wanted.split(",")));
        PrintWriter writer = new PrintWriter(new FileWriter(out));
        writer.println("program=" + currentProgram.getName());
        writer.println("language=" + currentProgram.getLanguageID());
        FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        while (functions.hasNext() && !monitor.isCancelled()) {
            Function function = functions.next();
            writer.println("function\t" + function.getName() + "\t" + function.getEntryPoint());
            if (!names.contains(function.getName())) {
                continue;
            }
            DecompileResults results = decompiler.decompileFunction(function, 60, monitor);
            writer.println("decompile_begin\t" + function.getName());
            if (results.decompileCompleted() && results.getDecompiledFunction() != null) {
                writer.println(results.getDecompiledFunction().getC());
                writer.println("decompiled=true\t" + function.getName());
            } else {
                writer.println("DECOMPILE_INCOMPLETE");
                writer.println("decompiled=false\t" + function.getName());
            }
            writer.println("decompile_end\t" + function.getName());
        }
        decompiler.dispose();
        writer.close();
    }
}
