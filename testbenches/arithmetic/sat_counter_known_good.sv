// testbenches/arithmetic/sat_counter_known_good.sv
// Hand-written known-correct saturating up/down counter.
module sat_counter #(
    parameter WIDTH = 4,
    parameter MAX_VAL = (1 << WIDTH) - 1
) (
    input  logic clk, rst_n,
    input  logic up, down,      // pulse to increment/decrement
    output logic [WIDTH-1:0] count
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= 0;
        end else begin
            if (up && !down) begin
                if (count < MAX_VAL) count <= count + 1;
            end else if (down && !up) begin
                if (count > 0) count <= count - 1;
            end
            // up && down simultaneously: hold (no change) -- explicit no-op
        end
    end
endmodule
