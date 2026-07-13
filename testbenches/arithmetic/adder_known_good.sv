// testbenches/arithmetic/adder_known_good.sv
// Hand-written, known-correct reference implementation.
// Used ONLY to validate the eval harness itself -- never presented as an
// LLM-generated result.
module adder #(parameter WIDTH = 8) (
    input  logic [WIDTH-1:0] a,
    input  logic [WIDTH-1:0] b,
    output logic [WIDTH:0]   sum
);
    assign sum = a + b;
endmodule
